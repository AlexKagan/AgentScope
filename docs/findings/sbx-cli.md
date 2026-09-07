# `sbx` CLI — empirical findings (Phase 1A.1, Step 1 spike)

This document records what was actually observed running the real `sbx`
(Docker Sandboxes) CLI, as opposed to what the Phase 1A.1 implementation plan
assumed. Treat this as ground truth for `SbxRuntimeConfig` and
`SbxSandboxRuntime` design; update it if a later `sbx` version changes any of
this behavior.

- **Version tested:** `v0.39.0` (`def8cb0523a77e757bdd6ef52b459fe374f3783e`).
  Pin this in `sbx-smoke.yml`.
- **Host tested on:** macOS 26.6.2 (Tahoe), Apple Silicon (arm64).

## Prerequisites (one-time, per machine)

1. Install: `brew trust docker/tap && brew install docker/tap/sbx`.
2. `sbx login` — interactive Docker account sign-in (opens browser). Required
   before any sandbox can be created.
3. `sbx policy init <allow-all|balanced|deny-all>` — a **global, machine-wide**
   network policy must be initialized once before `sbx create` will succeed.
   This is not scoped to one project/user session; it affects all sandboxes
   created on that machine until changed. We initialized `deny-all` for this
   project (matches the Phase 1A.1 default-deny target and
   `THREAT_MODEL.md`'s network-disabled baseline).

CI implication: `sbx-smoke.yml` must call `sbx policy init deny-all` (or
verify it's already set) before running any test that creates a sandbox.

## Lifecycle

```
sbx create shell <path> [--name NAME] [--cpus N] [--memory SIZE] [--deny-network ...]
       │
sbx exec <name> <argv...>        # repeatable; reuses the same sandbox
       │
sbx stop <name>                  # halts; sandbox state retained, resumable
       │
sbx exec <name> ...              # auto-restarts a stopped sandbox — confirmed
       │
sbx rm -f <name>                 # final teardown; removes container + state
```

- `sbx create` is fundamentally agent-shaped: `sbx create AGENT PATH...`. The
  `shell` agent (`sbx create shell <path>`) is the one suited to generic
  command execution — matches the plan's "use the shell sandbox mode."
- `sbx exec` on a **stopped** sandbox transparently restarts it before running
  the command — verified empirically.
- `sbx rm -f` actually removes the sandbox; confirmed via `sbx ls --json`
  returning `{"sandboxes":[]}` afterward.
- `sbx ls --json` gives machine-readable status/workspace list — usable for
  lifecycle assertions in tests without parsing human-readable output.

## Workspace mounting

**The workspace is mounted inside the sandbox at the identical host path**,
not at a fixed mount point. E.g. mounting
`/tmp/agentscope-run-xyz/workspace` makes it available inside the sandbox at
that same absolute path — there is no `/workspace` normalization done by
`sbx` itself.

`/workspace` does not exist in the real `shell` agent image; its native home is
`/home/agent`. The backend therefore leaves `HOME` unset in its explicit base
environment and retains the image's working default. Environment allowlisting
is enforced inside `SbxSandboxRuntime.execute()`, not delegated to callers.

Host↔sandbox file visibility is immediate and bidirectional: a file written
from the host is instantly readable from inside the sandbox, and a file
written from inside the sandbox is instantly visible via a normal host `cat`.
No explicit sync/flush step was needed.

`-w <path>` sets the working directory for `sbx exec` as expected (equivalent
to `docker exec -w`).

## argv fidelity (no shell reinterpretation)

Passed deliberately hostile-looking strings as **plain argv elements** (e.g.
via `python3 -c "..."`) — `"; rm -rf /"`, `"$(env)"`, `"hello && something"` —
and got them back byte-for-byte as literal string contents, never
reinterpreted by a shell. Confirms `sbx exec SANDBOX COMMAND [ARG...]` is safe
to drive with argv-based subprocess invocation (no `shell=True`, no manual
string building) as planned for the `_sbx_cli.py` boundary.

## Environment variables

- **No host inheritance by default.** A variable set only on the host
  (`AGENTSCOPE_SECRET_SENTINEL`) was confirmed absent inside the sandbox
  without any explicit `-e`.
- **Explicit `-e KEY=VALUE` works as expected** — value present and correct
  inside the sandbox.
- **⚠️ Bare `-e NAME` is dangerous — confirmed, not just theoretical.**
  `sbx exec -e AGENTSCOPE_HOST_ONLY_VAR ...` (bare name, no `=value`) silently
  copied the value from **the environment of the local process invoking
  `sbx`** (i.e. the AgentScope host process) into the sandbox. This is a live
  secret-leak path if any code path ever builds a bare `-e NAME` argument
  from a request that happens to name a variable that's also set on the
  AgentScope host.
  - **Hard rule for `_sbx_cli.py`:** always emit `-e NAME=value`. Never emit
    a bare `-e NAME`. Add a unit test (`test_sbx_invocation_never_uses_bare_env_name`,
    already scoped in the plan's Step 6) asserting every `-e` argument
    produced by the CLI boundary contains an `=`.

## Resource limits

- **CPU:** `--cpus N` is honored. `--cpus 1` → `nproc` inside the sandbox
  reported `1`.
- **Memory:** `--memory SIZE` is honored, **but has an enforced minimum of
  1 GiB.** `--memory 512m` was rejected outright:
  `ERROR: request failed: 400 Bad Request: invalid memory "512m": memory 512m
  is below the minimum of 1 GiB`. `--memory 1g` succeeded; `/proc/meminfo`
  inside the sandbox confirmed ~1 GiB total.
  - **`SbxRuntimeConfig` must validate `memory_limit >= 1 GiB`**, not merely
    "positive," or sandbox creation will fail at the `sbx` layer instead of
    failing fast in config validation.
- Each sandbox runs its own microVM with its own kernel (confirmed via
  `uname -a` showing a distinct kernel build per sandbox), not a shared-kernel
  container — cgroup inspection paths standard to Docker containers
  (`/sys/fs/cgroup/memory.max`) were not present; use `/proc/meminfo` /
  `nproc` instead for any black-box resource-limit assertions.

## Python version baseline (post-audit finding)

The `shell` agent's sandbox image (`docker/sandbox-templates:shell-docker`)
ships **Python 3.14.4**, confirmed via `sbx exec <sandbox> python3
--version`. This matches the DoD requirement ("Python 3.14 remains the
sandbox baseline"), but was initially true only by chance — nothing checked
it. Now enforced by
`tests/external/test_sbx_execute.py::test_sandbox_python_version_matches_expected_baseline`,
which compares the sandbox's reported `major.minor` against the
`EXPECTED_SANDBOX_PYTHON_VERSION` constant in
`tests/external/_sbx_baseline.py` (currently `"3.14"`) and fails loudly on any
mismatch — confirmed by deliberately
setting it to `"3.13"` and observing a clear, actionable failure.

**To change the required baseline** (e.g. to Python 3.15): update
`EXPECTED_SANDBOX_PYTHON_VERSION` in `tests/external/_sbx_baseline.py`,
re-run `uv run pytest -m sbx`, and update this note once the new version's
behavior has been re-verified — do not just bump the constant to make the
test pass without checking whether anything else in this findings doc
depended on the old version.

## Network isolation

Under the global `deny-all` policy, `curl https://example.com` from inside
the sandbox returned **HTTP 403**, not a connection-refused/timeout error —
egress appears to be proxied/intercepted rather than dropped at the network
layer. Local command execution inside the sandbox was unaffected.

Raw TCP connection establishment may also report success because the
transparent policy proxy accepts the local side of `connect()`. This is not
evidence that traffic reached the destination. The black-box suite therefore
uses a controlled host listener and asserts that no sandbox connection or
payload reaches it, rather than asserting that `connect()` itself fails.

**Test-writing implication:** black-box network-isolation tests should assert
"non-2xx / blocked response," not assume a raw connection error.

## ⚠️ Timeout / kill semantics — the most important finding

**This is Case B from the plan's Step 9, now proven empirically, not
assumed:**

Started a long-running remote loop (`while true; do date >> heartbeat.txt;
sleep 0.2; done`) via `sbx exec`, then sent `SIGTERM` and later `SIGKILL` to
the **local** `sbx exec` process.

Result: the remote heartbeat loop **kept running and kept appending to the
file** for many seconds after the local `sbx exec` process was gone (dozens
of additional heartbeat lines written after both the local process's death
and well past a reasonable timeout window). Killing the local CLI process
does **not** stop the remote command — the two are decoupled.

The only action that actually stopped the remote process was **`sbx stop
<sandbox>`**: heartbeat writes went flat immediately and stayed flat.
`sbx rm -f` also works for final teardown.

### Architectural consequence

Because Step 4 of the plan calls for **one persistent sandbox reused across
multiple commands in a run**, and the only proven way to actually kill a
runaway remote command is to stop the whole sandbox, a single command timeout
must be treated as **fatal to the entire sandbox**, not just to that one
command:

```
timeout
   → terminate local `sbx exec` process (best-effort; does not stop remote work)
   → sbx stop <sandbox>              (this is what actually kills the remote process)
   → mark the SbxSandboxRuntime instance CLOSED / unusable
```

A timed-out command burns the sandbox for the remainder of that AgentScope
run. Any caller issuing multiple commands through one runtime must be
prepared for the runtime to become invalid mid-run after a single timeout.
Implemented in Step 9 and formalized in **ADR 0011**.

## Sandbox-scoped network deny (Step 11)

`sbx create --deny-network RESOURCES` and `sbx policy deny network RESOURCES`
take a comma-separated list of hostnames/domains/IPs, **or the wildcard
`"**"` to block all outbound traffic** (`sbx policy deny network --help`).
Confirmed empirically: `sbx create shell <path> --deny-network "**"` blocks
egress the same way (`curl` → HTTP 403) as the global `deny-all` policy, but
scoped to that one sandbox — so AgentScope's isolation doesn't depend on
whatever the host machine's global policy happens to be. Wired into
`SbxCli.build_create_argv(..., deny_network=True)` (the default).

## Known gap: a vanished sandbox cannot be distinguished from a real exit code (Step 13)

`sbx exec` on a sandbox name that no longer exists returns **exit code 1**
with an error message on stderr (`"ERROR: no sandbox named '<name>'"`) —
confirmed empirically the same exit code (`1`) a real user command like
`sh -c 'exit 1'` produces on an existing sandbox. There is no distinct,
documented exit code for "sbx itself failed" (contrast Docker's own
convention of reserving 125–127 for daemon-level failures). The only
distinguishing signal is unstructured stderr text, which is not a stable API
to parse.

**Team decision:** document rather than build fragile stderr pattern-matching
(`docs/findings/sbx-cli.md` is not the place to encode a dependency on
undocumented CLI wording that could silently break on a future `sbx`
version). Confirmed and accepted in
`tests/external/test_sbx_error_normalization.py`: if a sandbox is removed
*externally* (not through the owning `SbxSandboxRuntime`'s own `close()`),
the next `execute()` call currently reports `ExecStatus.COMPLETED,
exit_code=1` rather than `ExecStatus.INFRA_FAILURE`. This does not affect
AgentScope's own lifecycle management (nothing in AgentScope removes a
sandbox out from under a live `SbxSandboxRuntime`) — it only matters if
something outside AgentScope interferes with a running sandbox.

## Open items not yet exercised by this spike

- `sbx cp` was not exercised (Step 12 plans to avoid it in favor of the
  mounted workspace anyway).
- Symlink-escape and path-traversal behavior specific to the real `sbx` mount
  (as opposed to AgentScope's own `resolve_within` validator) was not yet
  black-box tested — scoped for Step 7/8.
- Concurrent `sbx exec` calls against the same sandbox were not tested.

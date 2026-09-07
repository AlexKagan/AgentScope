# ADR 0011 — A command timeout invalidates the whole sandbox, not just the command

## Status
Accepted (Phase 1A.1).

## Context
Phase 0 defined `ExecStatus.TIMED_OUT` as a normal, representable outcome of
`execute()` — no assumption was made about what happens to the underlying
process once a timeout is reported. Phase 1A.1's Step 1 spike tested this
empirically against the real `sbx` backend: a long-running remote command was
started, then the local `sbx exec` process was sent `SIGTERM` and later
`SIGKILL`.

The remote command kept running and kept modifying the workspace for many
seconds after the local process was gone. Killing the local CLI process does
not stop the remote command — the two are decoupled. The only action that
actually stopped it was `sbx stop <sandbox>` (confirmed: a continuously
updated heartbeat file went flat immediately and stayed flat).

`SbxSandboxRuntime` is designed around one persistent sandbox reused across
many `execute()` calls in a run (Step 4). Given the above, the only way to
guarantee "when `timed_out == True`, the remote command is no longer
executing" is to stop the entire sandbox — there is no narrower operation
that kills just the one runaway command while leaving the sandbox otherwise
usable.

## Decision
On a command timeout, `SbxSandboxRuntime.execute()`:
1. Issues `sbx stop <sandbox>` and checks the result.
2. If stop fails, attempts `sbx rm -f <sandbox>` as the termination fallback.
3. Transitions the runtime to an internal `INVALID` state, distinct from
   `CLOSED`: the sandbox process is stopped but not yet removed.
4. Returns `TIMED_OUT` only after stop or removal confirms termination. If
   neither succeeds, returns `INFRA_FAILURE` and preserves retryable cleanup.

From `INVALID`, further `execute()` calls raise `SandboxClosedError`
deterministically — the runtime cannot be silently reused after a timeout.
`close()` performs `sbx rm -f` from `INVALID` or `READY`. It transitions to
`CLOSED` only after confirmed success; failures raise `SandboxCleanupError`
and remain retryable.

## Consequences
- A single command timing out burns the entire sandbox for the rest of that
  run. Any caller issuing multiple commands through one `SbxSandboxRuntime`
  must be prepared for the runtime to become unusable mid-run after one
  timeout, and must construct a new runtime (a new sandbox) to continue.
- Workspace writes are not transactional. Files produced before termination
  remain available for diagnostics but may be partial or inconsistent; callers
  decide whether to inspect, discard, or remount that workspace.
- This is proven, not assumed: `tests/external/test_sbx_timeout.py` verifies
  against the real backend that a continuously-updated file inside the
  workspace genuinely stops changing once `execute()` reports `TIMED_OUT`.
- The `ExecResult` contract itself did not need to change — `TIMED_OUT` was
  already representable in Phase 0. Only `SbxSandboxRuntime`'s internal
  lifecycle handling changed.
- See `docs/findings/sbx-cli.md` for the full empirical spike write-up.

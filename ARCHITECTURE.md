# AgentScope Architecture

> Agent topology is an experimental variable. Harness infrastructure and its
> security boundaries are the stable platform.

## Stable platform vs. replaceable agent architecture

AgentScope separates two concerns that are usually entangled:

- **The harness** — configuration, the sandbox-runtime contract, telemetry,
  security policy, and the composition root. This is the product. It changes
  slowly and under review.
- **Agent architectures** — simple tool use, planner/executor, validator
  subagents, async delegation, memory-augmented agents. These are experiments.
  Each owns its own state, control flow, prompts, roles, and scheduling.

An architecture plugs into the harness through the `AgentArchitecture` contract
and the `ArchitectureRegistry`. Adding one must not require changes to config
loading, telemetry, the runtime contract, or security policy.

## Phase 0 scope

Phase 0 built only the seams: configuration, telemetry, the composition
root, and the backend-independent `SandboxRuntime` protocol. There was **no
runnable agent** and **no concrete sandbox backend**. See
`AgentScope_Phase0_Foundation_System_Design_v2.md` for the full
specification and `docs/adr/` for the decisions.

## Phase 1A.1 scope

Phase 1A.1 adds the first concrete `SandboxRuntime` implementation:
`SbxSandboxRuntime`, backed by the real `sbx` (Docker Sandboxes) CLI. There
is still **no runnable agent** — that remains a separate axis (Phase 1A+,
`AgentArchitecture`/`ArchitectureRegistry`). What changed is that the
runtime contract Phase 0 defined only as a `Protocol` now has a real,
security-tested backend: sandbox lifecycle (create/reuse/close), command
execution with argv fidelity, environment isolation, filesystem isolation,
timeout/orphan-process handling, resource limits, and network isolation are
all verified against the actual `sbx` binary, not just fakes. See
`AgentScope_Phase1A1_Concrete_SandboxRuntime_Implementation_Plan.md`,
`src/agentscope/runtime/README.md`, `docs/findings/sbx-cli.md`, and ADR 0011
for the details.

## Capability layers

```
Clients (later)
      |
AgentService (Phase 1A+)
      |
ArchitectureRegistry ----> AgentArchitecture implementation (Phase 1A+)
      |
+---------------- stable platform capabilities ----------------+
| models | tools | runtime | policy | telemetry | persistence |
+-------------------------------------------------------------+
```

Phase 0 delivered `config`, `architectures`, `runtime` (contract only),
`telemetry`, and `bootstrap`. Phase 1A.1 adds a concrete `runtime` backend
(`SbxSandboxRuntime`) without touching any other package.

## Packages and dependency rules

| Package | Owns | Must not own |
|---|---|---|
| `bootstrap` | Composition root; loads config; constructs trusted deps | Agent topology; model-visible state |
| `architectures` | Architecture contract, identity, registry | Shared runtime implementations |
| `config` | Typed public + secret settings; validation; safe serialization | Provider-client construction |
| `runtime` | `SandboxRuntime` protocol; safe request/result types; env + workspace policy; the concrete `sbx` (Docker Sandboxes) backend (Phase 1A.1) | Model-visible tool wiring; agent control flow |
| `telemetry` | Telemetry contract; sanitizer; no-op/in-memory + Phoenix exporters | Business / architecture control flow |

**Dependency direction is inward toward contracts.** Platform packages must not
import concrete architecture implementations except at the
composition/registration boundary. `config` is a leaf. Only `bootstrap` (plus a
narrow, documented exception in `telemetry.phoenix`) imports
`agentscope.config.secret`.

## Architecture identity

Every architecture exposes `architecture_key` (stable registry identity, e.g.
`simple_tool_agent`) and `architecture_version` (explicit behavior version).
These exist now so later reproducible evaluation (Phase 1B) can attribute a
result change to the architecture rather than the model, prompt, tool schema,
runtime, or policy. The full evaluation `configuration_id` is deferred.

## Trust model

See `THREAT_MODEL.md`. In short: the model and everything it causes to run are
untrusted even though the provider is trusted; raw secrets live only in the
composition root and are converted into narrow injected capabilities; the
sandbox gets an allowlisted environment and only the task workspace.

# ADR 0004 — `SandboxRuntime` is a protocol; Docker Sandboxes come in Phase 1A

## Status
Accepted (Phase 0).

## Context
Model-facing execution must eventually run in an isolated sandbox with strict
env, path, network, and resource controls. Building that backend now would pull
Phase 1A work into the foundation.

## Decision
Phase 0 defines `SandboxRuntime` as a backend-independent `Protocol` in the
`runtime` package, plus boundary-safe `ExecRequest` / `ExecResult` types and the
env/path policies. No production runtime is implemented. Contract tests use
fakes. Docker Sandboxes implement the protocol in Phase 1A.

## Consequences
- The contract is written so later security requirements are representable
  (explicit workspace root, pre-filtered env, workspace-relative cwd, explicit
  timeouts/limits, typed outcome categories).
- Phase 0 makes no claim that real process termination, isolation, or mount
  behavior is verified — that is a Phase 1A/2 acceptance concern.

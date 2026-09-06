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

## Amendment (Phase 1A.1) — `close()` joins the protocol

Implementing the real `sbx` backend surfaced a concrete incompatibility: a
sandbox is an expensive, stateful external resource, and code holding only a
`SandboxRuntime`-typed reference had no way to guarantee it gets released.
Pushing cleanup onto caller discipline (a concrete-type cast, `hasattr`
checks) risks leaked sandboxes — the opposite of Phase 0's disciplined
approach to lifecycle. `SandboxRuntime` now also declares `close() -> None`,
required to be idempotent. `FakeSandboxRuntime` and `SbxSandboxRuntime` both
implement it; the shared contract suite (`tests/contract/`) exercises
idempotency on the fake, and `SbxSandboxRuntime`'s own unit tests
(`tests/unit/test_sbx_sandbox_runtime.py`) exercise it against a scripted
`sbx` CLI double.

# ADR 0008 — Expose only the task workspace; build sandbox env by allowlist

## Status
Accepted (Phase 0).

## Context
Two classic leaks: the sandbox inheriting the host environment (and its
secrets), and model-facing path operations escaping into host files
(`.env`, credential stores, AgentScope source).

## Decision
- **Environment:** `build_sandbox_environment` starts from an empty baseline
  plus sandbox-local literals, and adds only explicitly allowlisted variables,
  used literally (no interpolation). It never reads `os.environ`. There is no
  model-facing capability to look up a host env var by name
  (`reject_host_env_lookup` always raises).
- **Filesystem:** only the task workspace is exposed. One validator
  (`resolve_within`) resolves every model-facing path under the canonical
  workspace root and rejects absolute paths, `..`, and symlink escapes.

## Consequences
- Every added forwarded variable needs an explicit rationale and test.
- Phase 0 proves these with policy tests; Phase 1A adds black-box checks from
  inside the real sandbox.

# ADR 0002 — Agent topology is an experimental variable

## Status
Accepted (Phase 0).

## Context
AgentScope exists to compare agent designs (simple tool use, planner/executor,
validator subagents, async delegation, memory-augmented). If topology and
harness are entangled, every new design forces infrastructure rewrites.

## Decision
Agent topology lives behind the `AgentArchitecture` contract and the
`ArchitectureRegistry`. The harness (config, runtime contract, telemetry,
policy, composition) is the stable product. Each architecture owns its own
state, graph nodes, prompts, roles, and scheduling; the platform owns lifecycle
and infrastructure.

## Consequences
- A new architecture registers without touching config loading, telemetry,
  runtime contracts, or security policy.
- Phase 0 keeps the contract minimal (identity only) so it does not prematurely
  encode one topology's assumptions.

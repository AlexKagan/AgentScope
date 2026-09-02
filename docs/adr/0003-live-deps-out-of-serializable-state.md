# ADR 0003 — Live dependencies stay out of serializable state

## Status
Accepted (Phase 0).

## Context
Later phases persist graph/agent state for durability and evaluation. If
authenticated clients, sockets, or file handles live in that state, they leak
into snapshots, traces, and run records — and cannot be rehydrated.

## Decision
Constructed clients and other live handles are injected at composition time and
held only by trusted infrastructure objects (e.g. `Platform`). They are never
placed in serializable architecture/graph state. `Platform.model_client` is
`repr`-suppressed.

## Consequences
- Snapshots and telemetry stay free of connection objects and, transitively, of
  the credentials inside them.
- Rotation is "recompose the trusted objects", not "mutate saved state".

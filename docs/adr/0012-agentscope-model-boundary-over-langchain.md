# ADR 0012 — AgentScope owns the model boundary; LangChain is an implementation detail

## Status
Accepted (Phase 1A.2).

## Context
Later packages — budgets, observability, evaluation, durable agent state — need
a single, stable representation of a model call: assistant text, structured tool
calls, finish information, token usage, and cost. LangChain gives us provider
plumbing (client construction, message conversion, tool binding) but its
result shapes (`AIMessage`, `usage_metadata`,
`response_metadata`) and its provider exception types are not a contract we want
those packages to depend on. If a LangChain minor release reshuffles
`usage_metadata`, usage and cost must not silently regress across the codebase.

## Decision
`agentscope.models` defines the public contract and owns all normalization:

- `ModelAdapter` (async `ainvoke`), `ModelRequest` / `Message` / `ToolDefinition`,
  `ModelResponse` / `ToolCall`, `LLMUsage`, `PriceCard` / `LLMCost`,
  `SafeModelIdentity` + `fingerprint`, `ModelRegistry`, and the `ModelError`
  taxonomy.
- Usage extraction happens exactly once, in the adapter (`normalize_usage`). No
  other component reads `usage_metadata` or a provider payload.
- LangChain `AIMessage`, `usage_metadata`, `response_metadata`, and provider
  exception types never leave `openai_compatible.py`. The raw response is never
  retained in a public result or durable state.
- `provider_metadata` on a `ModelResponse` is an allowlisted, scalar-only subset
  (`model_name`, `finish_reason`, `system_fingerprint`, `service_tier`).

An import-boundary test keeps `langchain*` / `openai` imports confined to
`agentscope.models.openai_compatible` and `agentscope.bootstrap`.

## Consequences
- One place to fix when a provider or LangChain metadata shape changes; a fixture
  matrix and live smokes guard it.
- `architectures/` consume only the protocol — never credentials or provider
  payloads.
- A second provider integration (Bedrock, Azure, …) implements the same
  `ModelAdapter` and reuses the contract suite; it does not widen the public API.

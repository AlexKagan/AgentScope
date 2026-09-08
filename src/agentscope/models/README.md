# `agentscope.models` — the model boundary (Phase 1A.2)

## Ownership
This package owns AgentScope's **public model contract** and the normalization
of everything that crosses it: the async `ModelAdapter` protocol, validated
requests and tool schemas, the normalized response and structured tool calls,
token usage, cost with provenance, safe identity and reproducibility
fingerprint, the stable-key registry, and the error taxonomy.

It does **not** own (design §12):

- tool execution or Tool Gateway policy (Phase 1A.4);
- the agent graph/loop or `SimpleToolAgent` (Phase 1A.5);
- token/cost budget enforcement (Phase 1A.6);
- retry orchestration (belongs above the adapter, with the run/budget layer);
- streaming, multimodal, provider fallback/routing, or live capability probing.

LangChain owns provider interaction, message conversion, and tool binding.
LangChain `AIMessage`, `usage_metadata`, `response_metadata`, and provider
exception types never escape `openai_compatible.py`.

## Public contracts
- `ModelAdapter` (`protocol.py`) — `async ainvoke(ModelRequest) -> ModelResponse`,
  `identity`, `async aclose()`. One `ainvoke` == one provider attempt; never retries.
- `ModelRequest`, `Message`, `ToolDefinition`, `Role` (`requests.py`) — frozen,
  validated at the boundary. No callable tools, no per-call identity overrides.
- `ModelResponse`, `ToolCall`, `ToolCallOrigin`, `FinishReason` (`responses.py`) —
  frozen normalization. Raw provider payloads are never retained.
- `LLMUsage` + `normalize_usage` (`usage.py`) — the single token-accounting type.
- `PriceCard`, `LLMCost`, `CostSource`, `calculate_cost` (`cost.py`) — `Decimal`
  arithmetic, precedence (provider-reported → configured → unknown), unknown is
  `None` + `unknown`, never `0.0`.
- `ModelDefinition`, `Capability`, `BUILTIN_PROVIDER_PROFILES`, `validate_endpoint`
  (`configuration.py`) — validated, frozen, safely serializable configuration.
- `SafeModelIdentity`, `ProviderProfile`, `fingerprint` (`identity.py`) —
  credential-free identity; the fingerprint covers every safe behavior-affecting
  setting and is stable across credential rotation.
- `ModelRegistry`, `ResolvedModel` (`registry.py`) — stable-key → (definition,
  adapter) with deterministic duplicate/unknown/identity-mismatch errors.
- `ModelError` and its taxonomy (`errors.py`).

`OpenAICompatibleChatAdapter` (`openai_compatible.py`) is **not** re-exported from
`__init__`; only `agentscope.bootstrap` constructs it.

## Dependencies
- **Inward (allowed):** nothing from other `agentscope` packages except that
  `agentscope.config.public` imports `configuration` for its typed model catalog.
- **Outward (who imports this):** `agentscope.bootstrap` (constructs adapters,
  builds the registry) and, later, `architectures/` (consume the protocol only —
  no credentials, no provider payloads).
- **Third-party:** `pydantic` (validation/immutability) everywhere;
  `langchain`, `langchain-openai`, `langchain-core`, `openai` **only** in
  `openai_compatible.py`, imported lazily from bootstrap so a model-free runtime
  configuration never loads a provider package.

## Failure modes
`ModelConfigurationError` (bad/unknown definition, unsafe endpoint, registry
misuse — raised before any I/O), `ModelCapabilityError`, `ModelAuthenticationError`,
`ModelAuthorizationError`, `ModelRateLimitError`, `ModelTimeoutError`,
`ModelConnectionError`, `ModelInvalidRequestError`, `ModelProviderError`,
`ModelResponseNormalizationError`. The original exception is always the chained
cause; messages carry no credentials, headers, request bodies, or raw responses.

## Tests
- `tests/unit/test_model_*.py` — configuration/identity, request/tool validation,
  usage matrix, cost matrix, error taxonomy, registry.
- `tests/contract/test_model_adapter_contract.py` — the reusable adapter contract
  run against a deterministic scripted LangChain chat model.
- `tests/component/test_composition_root.py` — eager construction, credential
  selection, no startup network, model-free startup.
- `tests/external/test_openrouter_smoke.py`, `tests/external/test_meta_model_api_smoke.py`
  — opt-in live provider smokes (`external` + `openrouter` / `meta_model_api`).

## Telemetry
This package emits nothing directly in Phase 1A.2. `provider_metadata` on a
`ModelResponse` is an allowlisted, scalar-only subset (`model_name`,
`finish_reason`, `system_fingerprint`, `service_tier`) intended to be safe for a
later telemetry layer to record.

## Security implications
Trust-boundary role: the adapter is the seam where a raw credential becomes a
narrow authenticated capability. The credential is passed to the adapter by
`agentscope.bootstrap` and is never stored on any serializable type, never in an
identity or fingerprint, and never in an error message. Endpoints are validated
(HTTPS, no user-info, no query secrets, no fragment, no `..`).

## Deferred work
Responses API mode, streaming/partial tool calls, multimodal, dedicated
provider connectors (only if a recorded compatibility finding proves the generic
adapter insufficient), authoritative provider-cost extractors per profile, and a
synchronous convenience facade. See `docs/plans/phase-1a.2-model-usage-cost.md`
§14 for the future-provider backlog.

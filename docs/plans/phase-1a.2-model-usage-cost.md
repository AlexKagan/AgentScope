# Phase 1A.2 implementation and test plan

**Status:** Proposed
**Target:** Phase 1A.2 — model integration, normalized usage, and cost
**Baseline:** Phase 1A.1 and `AgentScope_System_Design_v8.3_restructured.md`
**Exit criterion:** Deterministic scripted tests pass, and opt-in OpenRouter and Meta-compatible smoke paths prove the same public model contract with native structured tool calling.

## 1. Purpose

Phase 1A.2 introduces the model boundary consumed by later agent architectures. It must let AgentScope invoke a configured chat model through LangChain without allowing LangChain- or provider-specific response shapes to leak into budgets, observability, evaluation, or durable agent state.

This increment delivers:

- an async AgentScope model protocol;
- one LangChain-based OpenAI-compatible Chat Completions adapter;
- a registry of stable model configuration keys;
- native structured-tool-call request and response normalization;
- normalized token usage;
- deterministic cost calculation with explicit provenance;
- normalized provider failures;
- eager local validation and lazy network invocation;
- scripted conformance tests and opt-in provider smoke tests;
- an explicit future-provider backlog.

## 2. Use cases

### UC-1: Invoke a configured model

An architecture selects a stable model configuration key. Runtime context resolves it to a live adapter and invokes it with messages and optional tool schemas. The result contains normalized assistant content, structured tool calls, finish information, usage, and cost.

### UC-2: Compare model configurations reproducibly

Two runs can use different providers, model names, reasoning options, or routing options. Every run records a safe canonical configuration identity without credentials.

### UC-3: Run without model access

Sandbox tests, configuration inspection, and other model-free operations start without model credentials and without importing or contacting a provider SDK.

### UC-4: Fail before agent-side effects

Unknown model keys, malformed endpoints, unsupported options, missing required credentials, and invalid tool schemas fail during composition or request validation, before a model request or tool action occurs.

### UC-5: Account for usage and cost

Callers consume one normalized usage and cost representation. They never parse provider payloads independently. Unknown cost remains unknown and is never converted to zero.

### UC-6: Validate real provider compatibility

Maintainers can manually run the same smoke contract against OpenRouter and a Meta Model API/Muse-compatible endpoint without exposing credentials to pull requests or deterministic CI.

## 3. Scope boundaries

### In scope

- LangChain chat-model integration.
- Non-streaming chat completion.
- Text assistant responses.
- Native structured tool calls, including multiple calls in one response.
- Provider-supplied tool-call IDs and JSON arguments.
- Token usage normalization.
- Provider-reported and configured-pricing cost calculation.
- Provider error normalization.
- OpenRouter and Meta Model API over Chat Completions, normalized through one AgentScope contract.
- Sync-free, async-first model invocation.

### Out of scope

- Tool execution and Tool Gateway policy (Phase 1A.4).
- Agent graph/loop and `SimpleToolAgent` (Phase 1A.5).
- Token and cost budget enforcement (Phase 1A.6).
- Model retry orchestration and retry budgets.
- Streaming responses and partial tool calls.
- Multimodal inputs or outputs.
- Automatic provider fallback or routing implemented by AgentScope.
- Model capability negotiation through live discovery.
- Dedicated OpenRouter adapter unless conformance testing proves the generic adapter insufficient.
- Bedrock, Azure OpenAI, Vertex AI/Gemini, Anthropic, or local inference implementation.

## 4. Decisions

### D1. Use an AgentScope boundary over LangChain

LangChain owns provider interaction, message conversion, and tool binding. AgentScope owns its public protocol and normalized result, usage, cost, identity, and error semantics.

LangChain `AIMessage`, `usage_metadata`, `response_metadata`, and provider exception types must not escape the adapter. This prevents later packages from depending on provider metadata layouts.

### D2. Start with one OpenAI-compatible implementation

`OpenAICompatibleChatAdapter` is configured with provider identity, base URL, model name, credentials, and safe request options. OpenRouter and Meta Model API both use `openai-chat-completions`. The Meta cookbook documents `client.chat.completions.create(...)` at `https://api.meta.ai/v1` with `muse-spark-1.3`, including native tool/function calling.

Responses API support is not part of Phase 1A.2. It should be introduced as a distinct protocol mode or adapter only when a concrete text, image, or provider-state use case requires it. The adapter must not switch protocols automatically.

A dedicated OpenRouter connector is postponed. It is introduced only if a recorded compatibility finding demonstrates a required feature that cannot be represented cleanly by the generic adapter, such as routing controls, authoritative cost metadata, attribution headers, streaming semantics, or materially different tool-call/error behavior.

### D3. Separate provider, protocol, model, and configuration identity

These are distinct:

- **configuration key:** stable user-facing selection, for example `primary-reasoner`;
- **provider/service:** `openrouter` or `meta`;
- **protocol:** `openai-chat-completions`;
- **model name:** provider model identifier;
- **configuration fingerprint:** hash of all safe behavior-affecting settings.

The fingerprint includes provider, protocol, model, endpoint identity, reasoning options, safe provider request options, pricing identity/version, adapter version, and tool-schema version. It excludes credentials and volatile client objects.

### D4. Eager validation, lazy I/O

At application composition:

1. validate model definitions and the selected key;
2. resolve the provider profile;
3. require only the credential needed by the selected model;
4. construct the local LangChain client and AgentScope adapter;
5. perform no network request.

The first `ainvoke` performs the first provider I/O. Authentication and connectivity therefore fail as normalized invocation errors, while configuration failures occur before the run starts.

### D5. Disable hidden retries

Configure the underlying LangChain client with implicit retries disabled (`max_retries=0`, or the equivalent supported by the pinned provider package). Phase 1A.2 performs one provider attempt per adapter invocation.

Retry policy belongs above the adapter so attempts, usage, cost, latency, and later budget consumption remain observable. Retry orchestration is deferred until its owning run/budget layer exists.

### D6. Async-first public protocol

The public model operation is `ainvoke`. Network I/O is naturally asynchronous and later service/LangGraph integration should not block an event loop. A synchronous wrapper is not added until a concrete caller requires it.

### D7. Cost has value and provenance

The cost result distinguishes:

- `provider_reported` — explicitly documented as authoritative for the call;
- `configured_pricing` — computed from a versioned price card;
- `unknown` — neither authoritative provider cost nor sufficient pricing exists.

Provider-reported cost wins. Configured pricing is the fallback. Unknown is represented as `None` plus source `unknown`, never `0.0`.

Use `Decimal` internally for prices and arithmetic. Convert provider numeric values through their string representation. Serialization uses a decimal string to avoid binary floating-point drift. If strict compatibility with the system-design `float | None` field is required, keep that field as provider input only and expose the authoritative normalized cost through the separate cost result.

### D8. No live capability probing during startup

Capabilities used by Phase 1A.2 are declared in the model definition and verified by contract/smoke tests. Startup must not spend tokens, add latency, or fail because a provider is temporarily unavailable.

## 5. Target architecture

```text
PublicConfig ── selected model configuration key
     │
     ▼
trusted composition root ── SecretConfig
     │                         │
     │ resolves definition    └── credential only
     ▼
ModelRegistry ─────────────► ModelAdapter (live, non-serializable)
                                 │
                                 ▼
                       OpenAICompatibleChatAdapter
                                 │
                                 ▼
                       LangChain provider client
                                 │
                      first I/O on `ainvoke`
                                 ▼
                     OpenRouter or Meta endpoint

provider response
     ▼
adapter normalization
     ├── ModelResponse
     ├── LLMUsage
     ├── LLMCost
     └── normalized ModelError
```

Only the configuration key and safe configuration identity may enter durable state. The registry, adapter, authenticated LangChain client, and credential remain runtime dependencies.

## 6. Proposed package structure

Create packages only with immediate Phase 1A.2 responsibility:

```text
src/agentscope/models/
├── __init__.py             # deliberately small public exports
├── protocol.py             # ModelAdapter protocol
├── requests.py             # validated request and tool-schema inputs
├── responses.py            # normalized response and tool-call types
├── usage.py                # LLMUsage validation/normalization helpers
├── cost.py                 # PriceCard, LLMCost, precedence/calculation
├── identity.py             # safe model identity and fingerprint
├── configuration.py        # model definitions and declared capabilities
├── registry.py             # stable-key registration/resolution
├── errors.py               # normalized model error taxonomy
└── openai_compatible.py    # LangChain implementation and response mapping
```

Also modify:

- `src/agentscope/bootstrap/clients.py` to construct typed adapters rather than `object`;
- `src/agentscope/bootstrap/composition.py` to expose a model registry/resolver in runtime context;
- `src/agentscope/config/public.py` for stable model selection and safe model definitions;
- `src/agentscope/config/secret.py` for provider-specific credential fields;
- `.env.example` for secret variable names only; public model and smoke configuration lives in typed configuration files;
- `pyproject.toml` and `uv.lock` to activate the required LangChain provider package;
- `src/agentscope/models/README.md` to document the package boundary;
- test markers and provider smoke workflows.

Do not put provider implementations in `architectures/`. Architectures consume the model protocol and cannot access credentials or provider payloads.

## 7. Domain contracts

The exact Python spelling is implementation work; the required semantics are below.

### 7.1 Model definition

A validated, frozen, safely serializable definition contains:

- stable configuration key;
- provider/service key;
- protocol key;
- model name;
- optional HTTPS base URL;
- credential reference by symbolic field name, never its value;
- request timeout;
- declared capabilities required now: text and structured tool calling;
- reasoning options;
- allowlisted provider request options;
- optional versioned pricing identity and prices;
- adapter implementation version.

Recommended operator-facing shape:

```yaml
primary_model_key: primary-reasoner
models:
  primary-reasoner:
    provider: meta
    protocol: openai-chat-completions
    base_url: https://api.meta.ai/v1
    model_name: muse-spark-1.3
    credential_ref: meta_model_api_key
    timeout_s: 60
    capabilities: [text, tool_calling]
```

The fields have intentionally different meanings:

- `provider` identifies the commercial/service boundary (`meta`, `openrouter`, `openai`); it is not a URL;
- `protocol` selects request/response semantics and the adapter mode;
- `base_url` identifies the endpoint and must be validated separately;
- `model_name` is the provider's model identifier;
- `credential_ref` names a permitted `SecretConfig` field; it never contains the secret;
- `primary_model_key` decouples architecture/run configuration from provider details.

The user's original three inputs—model name, provider endpoint, and credential—remain the essential deployment inputs. The additional provider/protocol/key fields prevent endpoint strings from becoming overloaded identifiers and make run records reproducible. For a small local configuration the registry can be built directly from this mapping; no separate database or provider catalog is needed.

Arbitrary provider kwargs are not accepted blindly. Maintain an explicit allowlist per profile so credentials, callbacks, unsafe endpoints, and behavior-affecting options cannot bypass validation or reproducibility identity.

### 7.2 Model request

A frozen request contains:

- normalized conversation messages;
- zero or more tool definitions;
- tool-choice mode when supported;
- request correlation/call ID;
- optional safe per-call options explicitly allowed by the selected definition.

Use LangChain message and tool-schema facilities inside the adapter, but validate at the AgentScope boundary. Phase 1A.2 does not accept callable tools because the model layer describes tools but never executes them.

Validation rejects:

- empty or unsupported message content;
- duplicate tool names;
- invalid JSON Schema;
- executable callbacks/callables;
- per-call model, provider, endpoint, credential, or pricing overrides;
- unsupported capability requests.

### 7.3 Model response

A frozen normalized response contains:

- optional assistant text;
- ordered structured tool calls;
- normalized finish reason when available;
- `LLMUsage`;
- `LLMCost`;
- safe provider metadata needed for diagnosis and reproducibility;
- model-call ID when supplied;
- raw provider response: **not retained** in durable state or public results.

Each tool call contains a provider call ID, tool name, and JSON-compatible argument mapping. Malformed arguments or missing IDs are normalization failures, not free-form text actions. If a compatible endpoint omits call IDs, generate a deterministic call ID from call position and model-call identity and mark its origin as generated.

### 7.4 Usage

`LLMUsage` follows the system design:

- `input_tokens: int`;
- `output_tokens: int`;
- `total_tokens: int`;
- `cached_input_tokens: int | None`;
- `reasoning_tokens: int | None`;
- `provider_reported_cost_usd` as untrusted normalized input when present.

Invariants:

- all token values are non-negative integers;
- required token fields must be present for a successful Phase 1A.2 call;
- `total_tokens == input_tokens + output_tokens` when the provider semantics match that definition;
- otherwise retain the provider total and record a safe discrepancy flag;
- cached input is a subset/accounting dimension, not added again to total;
- reasoning tokens are a subset of output unless provider documentation states otherwise;
- absent optional dimensions remain `None`, not zero;
- malformed, boolean, negative, or non-integral values fail normalization.

Usage extraction is centralized in the adapter. No downstream component reads LangChain `usage_metadata` or provider response dictionaries.

### 7.5 Cost

A versioned price card initially supports USD per one million tokens for:

- uncached input;
- cached input;
- output.

For configured pricing:

```text
uncached_input = input_tokens - cached_input_tokens
cost = (
    uncached_input × input_rate
  + cached_input_tokens × cached_input_rate
  + output_tokens × output_rate
) / 1_000_000
```

Rules:

- reject cached tokens greater than input tokens;
- if cached usage exists but no cached rate is configured, apply an explicit price-card policy: use the input rate or declare cost unknown; the selected policy is part of pricing identity;
- reasoning tokens are not charged separately unless a future provider price card explicitly defines that dimension;
- never infer provider authority merely because a response contains a field named `cost`;
- an authoritative provider-cost extractor is provider-profile code covered by tests;
- do not round during accumulation; round only for presentation.

### 7.6 Error taxonomy

Expose stable error categories while preserving the original exception as a chained cause:

- `ModelConfigurationError`;
- `ModelCapabilityError`;
- `ModelAuthenticationError`;
- `ModelAuthorizationError`;
- `ModelRateLimitError`;
- `ModelTimeoutError`;
- `ModelConnectionError`;
- `ModelInvalidRequestError`;
- `ModelProviderError`;
- `ModelResponseNormalizationError`.

Error messages and safe metadata must not contain credentials, authorization headers, complete request bodies, or raw provider responses. The adapter does not retry.

## 8. Configuration and lifecycle migration

### 8.1 Stable keys

The current `primary_model="provider:name"` parser conflates selection with provider/model identity. Phase 1A.2 should migrate to:

- `primary_model_key`: a stable key such as `primary-reasoner`;
- a validated model-definition catalog supplied to composition;
- `ModelRegistry.resolve(primary_model_key)` returning the canonical definition and live adapter.

Because the project is pre-release, prefer a clear breaking migration over maintaining two ambiguous formats. If compatibility is temporarily required, parse the legacy value only at the configuration edge, emit a deprecation warning, and immediately convert it to a generated definition. Do not support both representations throughout the core.

The current `PublicConfig` also loads `.env` through `BaseSettings`. Migrate public settings to the selected typed configuration-file/CLI source so `.env` is exclusively a local secret carrier. Environment overrides for public settings should not be added implicitly; if operational overrides are later required, design them as an explicit, allowlisted configuration layer.

### 8.2 Secrets

Add distinct optional secret fields for the initial profiles:

- `openrouter_api_key`;
- `meta_model_api_key`, loaded from `AGENTSCOPE_META_MODEL_API_KEY`.

Do not reuse `openai_api_key` merely because the wire protocol is OpenAI-compatible. Secret selection follows provider identity, not protocol identity.

`SecretConfig` remains consumable only by `agentscope.bootstrap`. The bootstrap layer extracts one credential and passes it directly to the client factory. Registry definitions and fingerprints contain only the symbolic credential reference.

### 8.3 Client lifetime

- Construct one client/adapter per canonical model definition during platform composition.
- Reuse the immutable adapter and its connection pool across runs when LangChain documents the client as concurrency-safe.
- Bind run-specific tool schemas without mutating the shared adapter/client.
- Close async clients during platform/service shutdown if the selected LangChain integration exposes a close operation.
- Add bounded cleanup ownership when `AgentService` is introduced; Phase 1A.2 documents and tests any currently available close behavior.

### 8.4 Endpoint policy

- Built-in provider profiles use pinned HTTPS base URLs.
- Custom OpenAI-compatible endpoints require explicit configuration and HTTPS by default.
- Local HTTP may be allowed only through an explicit development-only setting.
- Endpoint URLs must reject embedded credentials, query-string secrets, fragments, and unexpected path rewriting.

## 9. Dependency plan

1. Move the LangChain packages required by the model implementation out of the speculative `future` extra and into an explicit `models` extra or the default runtime dependencies, depending on whether model-free minimal installation remains a product requirement.
2. Add and pin the LangChain OpenAI provider integration compatible with the repository's LangChain version (normally `langchain-openai`); do not assume the base `langchain` package supplies `ChatOpenAI`.
3. Keep imports lazy from bootstrap if model-free startup without the extra is supported. Produce a focused installation error rather than an import traceback.
4. Regenerate `uv.lock` and run the full Python 3.13/3.14 matrix.
5. Record the exact provider-package versions in live-smoke diagnostics.

Recommended choice for Phase 1A.2: make model support a first-class default dependency because it is now implemented product functionality. Preserve model-free **runtime configuration**, not a partially installed runtime. This reduces CI combinations and avoids a feature that exists in source but is absent from the standard installation.

## 10. Implementation sequence

Every step follows red-green-refactor: add the specified deterministic test first, implement the minimum public behavior, then run the complete deterministic suite.

### Step 1: Freeze contracts and ADRs

- Add an ADR for AgentScope-over-LangChain normalization.
- Add an ADR for generic OpenAI-compatible first and evidence-gated dedicated adapters.
- Add an ADR for eager validation/lazy provider I/O and disabled implicit retries.
- Resolve the two open decisions in Section 15 before contract implementation.

**Gate:** ADR review agrees on ownership, lifecycle, and stable-key semantics.

### Step 2: Add immutable identities and configuration

- Implement model definition, provider profile, declared capabilities, pricing identity, and safe fingerprint.
- Migrate primary model selection to a stable key.
- Add provider-specific secret references and update secret-boundary tests.
- Reject unknown keys and unsafe configuration before client construction.

**Gate:** configuration/identity unit tests and existing secret-hygiene tests pass.

### Step 3: Define normalized protocol and types

- Implement request, tool definition, response, tool call, usage, cost, and error types.
- Define async `ModelAdapter` protocol.
- Keep implementation/provider types out of public modules.

**Gate:** type checking proves a fake adapter satisfies the protocol; validation tests cover all invariants.

### Step 4: Implement usage and cost independently

- Build table-driven usage normalization helpers.
- Build `Decimal` price-card calculation and source precedence.
- Define authoritative provider-cost extractor interface/profile hook.
- Test unknown cost explicitly.

**Gate:** exhaustive unit matrix passes without LangChain or network access.

### Step 5: Implement registry and composition

- Register canonical definitions by stable key.
- Reject duplicates and mismatched identity.
- Construct local adapters at composition without network I/O.
- Preserve startup without models/credentials when no model is selected.
- Replace `Platform.model_client: object | None` with the narrow typed model capability/registry.

**Gate:** component tests prove eager validation, correct credential selection, no startup network, safe repr/serialization, and model-free startup.

### Step 6: Implement the LangChain adapter

- Construct the provider client with explicit base URL, model, timeout, and zero implicit retries.
- Convert normalized request messages at the boundary.
- Bind JSON-schema tools without callable execution.
- Invoke asynchronously.
- Normalize text, ordered tool calls, usage, safe metadata, finish reason, and provider call ID.
- Calculate cost exactly once after usage normalization.
- Translate supported provider/LangChain errors into the stable taxonomy.

**Gate:** scripted adapter contract passes against a fake LangChain chat model and representative raw response fixtures.

### Step 7: Add reusable adapter contract suite

- Define a factory fixture that can run the same behavioral tests against scripted, OpenRouter, and Meta-compatible implementations/profiles.
- Keep external assertions provider-neutral.
- Allow provider-specific finding tests only where the provider contract genuinely differs.

**Gate:** scripted contract covers the matrix in Section 11.3.

### Step 8: Add live provider smokes

- Add one OpenRouter smoke and one Meta-compatible smoke.
- Use inexpensive, explicitly configured models.
- Exercise plain text and forced structured tool calling.
- Assert normalized usage and cost-source semantics.
- Record safe diagnostic identity, never prompts containing secrets or raw headers.

**Gate:** both smoke paths pass locally with credentials and are runnable through separate opt-in workflows.

### Step 9: Documentation and closure

- Update root and package READMEs, `.env.example`, system status, and roadmap status.
- Add findings documents for any provider incompatibility.
- Run lint, format, strict mypy, deterministic tests, secret scan, and both live smokes.
- Confirm no raw LangChain/provider types are imported outside `agentscope.models` and bootstrap.

**Gate:** all Phase 1A.2 exit criteria in Section 13 are checked.

## 11. Test plan

### 11.1 Unit tests

#### Configuration and identity

- valid model definition and capability declaration;
- invalid/embedded-credential endpoint;
- unknown protocol/provider profile;
- unknown selected model key;
- duplicate configuration key;
- safe deterministic fingerprint;
- fingerprint changes for every behavior-affecting option;
- fingerprint does not change for credential rotation;
- secret values absent from repr, dump, fingerprint, errors, and logs;
- legacy `provider:name` behavior matches the selected migration policy.

#### Request and tool validation

- text messages in supported roles;
- empty/unsupported content rejection;
- valid object JSON Schema;
- duplicate tool names;
- invalid schema;
- callable/executable tool rejection;
- unsupported tool-choice/capability;
- per-call endpoint/model/credential override rejection.

#### Usage normalization

- normal prompt/completion/total usage;
- cached input present and absent;
- reasoning tokens present and absent;
- zero-token values preserved as zero;
- absent optional values preserved as `None`;
- missing required usage;
- negative, boolean, float, string, and malformed usage;
- provider total discrepancy handling;
- provider metadata variants represented by scripted fixtures.

#### Cost calculation

- provider-reported authoritative cost takes precedence;
- configured input/output calculation;
- cached-input discounted calculation;
- cached tokens with fallback-to-input-rate policy;
- cached tokens with unknown-cost policy;
- missing price card produces unknown, not zero;
- partial price card produces unknown;
- zero tokens with known pricing produces known zero;
- decimal precision and no premature rounding;
- invalid negative rate/usage;
- cached tokens greater than input;
- pricing identity included in result/fingerprint.

#### Error normalization

- authentication;
- authorization;
- rate limit;
- timeout;
- connection failure;
- invalid request;
- generic provider 5xx;
- malformed successful response;
- original exception is chained;
- normalized messages contain no request headers, keys, or raw body;
- no retry occurs.

### 11.2 Component tests

- platform with no selected model builds without credentials or provider imports/network;
- selected model requires exactly its referenced credential;
- OpenRouter selection does not require an OpenAI or Meta key;
- Meta selection does not require an OpenAI or OpenRouter key;
- client is constructed during composition;
- construction performs no DNS/HTTP operation;
- malformed configuration fails before client construction;
- shared adapter is not mutated by run-specific tool binding;
- safe configuration snapshot is serializable;
- live client cannot enter durable/public configuration;
- adapter close is idempotent if close ownership is implemented now.

### 11.3 Reusable adapter contract

Run against a deterministic scripted LangChain model:

| Case | Required assertion |
|---|---|
| Plain text | Exact normalized text, no tool calls |
| One forced tool call | Name, call ID, JSON arguments, order |
| Multiple tool calls | All calls retained in provider order |
| Text plus tool call | Both retained without free-form parsing |
| Empty assistant text with tool call | Valid structured response |
| Unknown returned tool | Preserved as a requested call; execution policy is later |
| Malformed tool arguments | Normalization error |
| Missing provider call ID | Deterministic generated ID and origin flag |
| Standard usage | All required token fields normalized |
| Cached/reasoning usage | Optional dimensions normalized |
| Authoritative provider cost | Provider value and provenance win |
| Configured pricing | Exact computed value and pricing identity |
| No cost data | Explicit unknown cost |
| Provider exception | Stable category and chained cause |
| Timeout | Normalized timeout; exactly one attempt |
| Concurrent invocations | No request/tool-binding state leakage |
| Cancellation | Cancellation propagates; not rewritten as provider failure |

Do not mock AgentScope normalization itself. Script only the LangChain/provider boundary and use realistic `AIMessage`/metadata shapes captured as sanitized fixtures.

### 11.4 External smoke tests

Each provider profile runs two calls:

1. **Plain response:** request a fixed short token such as `READY`; assert non-empty normalized text and no tool calls.
2. **Structured call:** bind a harmless synthetic `lookup_temperature(city: string)` schema and force/select it; assert the returned call name, JSON object arguments, ID, usage, and cost provenance. Never execute the tool.

External assertions must tolerate natural-language variation and provider-generated IDs. They must not assert exact token counts or cost amounts.

#### OpenRouter smoke

- marker: `external` + `openrouter`;
- secrets: `AGENTSCOPE_OPENROUTER_API_KEY`;
- typed public model configuration: explicit smoke model and built-in HTTPS endpoint;
- confirm the generic `OpenAICompatibleChatAdapter` is used;
- assert cost is `provider_reported` only when the implemented extractor is documented as authoritative; otherwise use configured pricing or unknown.

#### Meta Model API smoke

- marker: `external` + `meta_model_api`;
- secrets: `AGENTSCOPE_META_MODEL_API_KEY`;
- typed public model configuration defaults: `https://api.meta.ai/v1`, `muse-spark-1.3`, and explicit `openai-chat-completions` mode; allow the smoke model to be overridden in that configuration because account availability may change;
- confirm the same adapter contract through LangChain `ChatOpenAI`;
- verify plain text and native function/tool calling as documented by the Meta cookbook;
- record any incompatibility in a findings document before adding a specialized adapter.

### 11.5 Security and hygiene tests

- extend seeded fake-secret fixtures with every new provider key;
- scan public config, model definitions, adapter/result reprs, exceptions, telemetry events, and serialized snapshots;
- assert authorization headers and base URLs with user-info/query secrets are rejected or sanitized;
- retain `SecretConfig` import/consumption restriction outside bootstrap;
- ensure scripted fixtures contain no real response IDs, account IDs, prompts, or credentials;
- run gitleaks after smoke-fixture updates.

### 11.6 Static and repository checks

- Ruff and format checks;
- strict mypy across `src` and tests;
- import-boundary test: LangChain provider imports are limited to model implementation/bootstrap;
- no `SecretConfig` outside bootstrap;
- no provider response parsing outside `agentscope.models`;
- deterministic suite passes without network and without provider credentials;
- Python 3.13 and 3.14 remain supported.

## 12. CI plan

### Deterministic CI

Update the normal `ci.yml` matrix to install the actual model dependencies and run all unit, component, contract, and integration tests with external tests excluded. No model credentials are available or required.

### Provider smoke workflows

Create separate workflows so providers have independent credentials, schedules, and failure attribution:

- `openrouter-smoke.yml`;
- `meta-model-api-smoke.yml`.

Both workflows:

- run only through `workflow_dispatch` initially;
- never run on pull requests;
- use GitHub environment/repository secrets;
- set a job timeout and per-request timeout;
- install from the frozen lock;
- run only the matching marker;
- avoid verbose HTTP/provider logging;
- upload no raw responses;
- report adapter/provider/model/package versions and normalized safe failure category;
- use concurrency limits to avoid duplicate spend.

After several stable manual runs, an informational low-frequency schedule may be added. A live-provider outage should not block deterministic pull-request CI.

Add markers:

- `openrouter`: real OpenRouter API;
- `meta_model_api`: real Meta-compatible API.

Both imply `external` by convention and must remain excluded by default.

## 13. Acceptance criteria

Phase 1A.2 is complete only when all items are true:

- [ ] `ModelAdapter` is typed, async, provider-neutral, and documented.
- [ ] OpenAI-compatible adapter is implemented with LangChain.
- [ ] Implicit provider-client retries are disabled.
- [ ] Stable configuration keys resolve through `ModelRegistry`.
- [ ] Provider/protocol/model/configuration identities are separate.
- [ ] Client construction is local/eager and first network I/O occurs on invocation.
- [ ] Model-free startup still works without credentials or network.
- [ ] Native structured tool calls work without free-form action parsing.
- [ ] Usage is normalized once into `LLMUsage`.
- [ ] Cost precedence and explicit unknown cost are implemented.
- [ ] Errors use the normalized taxonomy and retain safe chained causes.
- [ ] Credentials and live clients cannot enter serializable state.
- [ ] Scripted adapter contract passes deterministically.
- [ ] Full existing deterministic suite remains green on Python 3.13 and 3.14.
- [ ] OpenRouter plain-text and structured-call smokes pass through the generic adapter.
- [ ] Meta-compatible plain-text and structured-call smokes pass through the same contract.
- [ ] Live smoke workflows are opt-in and isolated from pull requests.
- [ ] Documentation, `.env.example`, package README, and system status are updated.
- [ ] Future-provider backlog is recorded and prioritized.

## 14. Future-provider backlog (`todo_in_future`)

This is a product-facing backlog, not Phase 1A.2 scope. Prioritization should be driven by client demand, deployment environment, required capabilities, and verified protocol incompatibility.

| Priority | Integration | Primary client use case | Expected approach | Promotion trigger |
|---|---|---|---|---|
| High | Azure OpenAI | Enterprise Azure, private networking, deployment names, Entra ID | Provider profile first; dedicated adapter if auth/API-version/deployment semantics require it | First Azure client or committed deployment |
| High | AWS Bedrock | Enterprise AWS/IAM, VPC endpoints, multiple model families | Dedicated adapter | First AWS client or committed deployment |
| High | Direct OpenAI | Baseline/reference provider | OpenAI-compatible profile | Needed for baseline or client deployment |
| Medium | Google Vertex AI / Gemini | Enterprise GCP/IAM and Gemini models | Dedicated adapter/profile based on selected API | First GCP client |
| Medium | Anthropic direct | Native Claude features and usage metadata | Dedicated adapter | Native capability required beyond Bedrock/OpenRouter |
| Medium | Self-hosted OpenAI-compatible | vLLM, SGLang, TGI, private inference gateways | Configurable OpenAI-compatible profile | Private/on-prem client requirement |
| Medium | LiteLLM or enterprise proxy | Central routing, audit, spend controls | Compatible profile plus gateway metadata if required | Gateway adopted by a client |
| Later | Local inference | Offline development, privacy, deterministic evaluation support | Capability-specific local profile/adapter | Validated evaluation use case |

For every promoted integration, require:

- authentication and credential-lifecycle design;
- endpoint/private-network configuration;
- capability matrix: tools, streaming, multimodal, reasoning, JSON mode;
- usage and authoritative-cost mapping;
- rate-limit and error taxonomy mapping;
- reproducibility identity rules;
- deterministic adapter contract;
- opt-in live smoke workflow;
- a compatibility finding justifying a dedicated adapter rather than a profile.

The backlog should be reviewed at the start of each model-integration increment. Provider names alone are not sufficient justification for new adapters.

## 15. Resolved decisions and remaining validation

No configuration-location decision remains: model definitions are authored in typed application configuration loaded at bootstrap, with programmatic injection available in tests. Phase 1A.2 does not add a database or plugin catalog.

The Meta endpoint, SDK contract, credential environment variable, initial model, and tool-calling capability are identified by the public Meta Model API cookbook: OpenAI-compatible Chat Completions at `https://api.meta.ai/v1`, `MODEL_API_KEY`, `muse-spark-1.3`, and native function/tool calling. AgentScope maps the external credential to its namespaced `AGENTSCOPE_META_MODEL_API_KEY` setting. The live smoke verifies this documented contract against the configured account.

Non-blocking follow-ups:

- whether streaming becomes Phase 1B work or a separate model-layer increment;
- when a synchronous convenience facade is justified;
- whether model support remains an install extra after Phase 1A.2;
- retention policy for sanitized raw-response fixtures.

## 16. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LangChain metadata shape changes | Usage/cost silently regress | Pin dependency, centralize parsing, fixture matrix, live smokes |
| “OpenAI-compatible” provider divergence | Tool calls or errors differ | Reusable contract and documented compatibility findings |
| Hidden retries | Untracked spend and latency | Disable client retries; later orchestration owns attempts |
| Provider-reported cost is mistaken as authoritative | Incorrect budgets/evaluation | Profile-specific authoritative extractor and provenance |
| Credentials leak through exceptions or repr | Security incident | Bootstrap-only secrets, sanitization tests, no raw responses |
| Model catalog conflates stable key with model name | Irreproducible configuration | Separate identities and fingerprint all safe behavior settings |
| Live tests are flaky or expensive | Noisy CI and unwanted spend | Opt-in isolated workflows, cheap model, two bounded calls |
| Shared client is mutated by tool binding | Cross-run contamination | Immutable adapter and concurrency contract test |
| Meta endpoint remains ambiguous | Cannot prove exit criterion | Resolve exact service before live-workflow implementation |

## 17. Deliverables

- `agentscope.models` package and package README;
- typed model adapter, request, response, usage, cost, identity, registry, and errors;
- LangChain OpenAI-compatible Chat Completions implementation;
- migrated bootstrap/configuration and provider-specific secrets;
- deterministic unit, component, security, and reusable contract suites;
- OpenRouter and Meta-compatible external smoke tests;
- two opt-in CI workflows;
- relevant ADRs and provider compatibility findings;
- updated root/system documentation;
- maintained `todo_in_future` provider backlog.

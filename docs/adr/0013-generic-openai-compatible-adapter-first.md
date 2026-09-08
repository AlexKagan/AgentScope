# ADR 0013 — One generic OpenAI-compatible adapter first; dedicated connectors are evidence-gated

## Status
Accepted (Phase 1A.2).

## Context
The first two target providers — OpenRouter and the Meta Model API — both speak
OpenAI-compatible Chat Completions (`client.chat.completions.create(...)`,
`https://api.meta.ai/v1`, `muse-spark-1.3`, native function/tool calling per the
Meta cookbook). Building a dedicated connector per provider now would multiply
code and tests before we have evidence that any provider needs one.

## Decision
Phase 1A.2 ships one `OpenAICompatibleChatAdapter` (LangChain `ChatOpenAI`),
configured per model with provider identity, pinned HTTPS base URL, model name,
credential, timeout, and an allowlist of safe request options. Provider identity
(`meta`, `openrouter`) is kept separate from protocol (`openai-chat-completions`),
model name, endpoint, and the stable configuration key.

A dedicated connector is added only when a **recorded compatibility finding**
(`docs/findings/`) shows a required feature the generic adapter cannot represent
cleanly: routing controls, authoritative cost metadata, attribution headers,
streaming semantics, or materially different tool-call / error behavior.
Responses API support is out of scope and must never be selected automatically —
it would be a distinct protocol mode or adapter.

## Consequences
- Two providers are proven against the same contract suite and two opt-in live
  smokes; provider-neutral assertions stay in the shared suite.
- The future-provider backlog (plan §14) tracks candidates; a provider name alone
  is not justification for a new adapter.
- If OpenRouter later needs routing/cost/header features, the finding that
  triggers the dedicated connector is written first.

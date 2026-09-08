# ADR 0014 — Eager model validation, lazy provider I/O, no implicit retries

## Status
Accepted (Phase 1A.2).

## Context
Model configuration errors (unknown key, unsafe endpoint, missing credential,
unsupported option, invalid tool schema) must fail before an agent run starts
side effects. Network and auth failures, by contrast, are properties of a call.
Separately, provider SDKs retry transparently by default; hidden retries make
spend, latency, usage, and (later) budget consumption unobservable.

## Decision
**Eager validation, lazy I/O.** At composition the bootstrap layer validates
model definitions and the selected key, resolves the provider profile, requires
only the credential the selected model references, and constructs the local
LangChain client and `OpenAICompatibleChatAdapter` — with **no** network request.
The first `ainvoke` performs the first provider I/O, so authentication and
connectivity surface as normalized `ModelError` invocation failures while
configuration problems surface before the run.

**No implicit retries.** The client is built with `max_retries=0`. One `ainvoke`
== exactly one provider attempt. The adapter never retries and never rewrites
`asyncio.CancelledError` as a provider failure. Retry orchestration belongs above
the adapter, with the run/budget layer that owns attempts, and is deferred until
that layer exists.

**No startup capability probing.** Capabilities are declared in the model
definition and checked by contract/smoke tests; startup spends no tokens and does
not fail because a provider is briefly unavailable.

## Consequences
- Model-free startup still works with no credentials, no network, and no provider
  package imported (the LangChain import is lazy in bootstrap).
- Component tests assert: construction does no DNS/HTTP, malformed config fails
  before client construction, and the credential selected matches the provider.
- When retry orchestration lands, it wraps the adapter; the adapter contract does
  not change.

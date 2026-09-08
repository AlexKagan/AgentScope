# AgentScope

An experimental agent-design platform. AgentScope treats **agent topology as an
experimental variable** and the **harness (infrastructure + security
boundaries) as the stable platform**, so new agent architectures plug in without
rewriting shared infrastructure.

This repository built its **Phase 0 — Foundation** first: the platform
boundaries (configuration, the sandbox-runtime contract, telemetry, security
policy, the composition root, tests, docs), with no runnable agent behavior
and no concrete sandbox backend. **Phase 1A.1** then added the first
concrete `SandboxRuntime` implementation — `SbxSandboxRuntime`, backed by
the real `sbx` (Docker Sandboxes) CLI — with its lifecycle, isolation, and
timeout guarantees verified against the real sandbox, not just fakes.
**Phase 1A.2** adds the model boundary: an async `ModelAdapter` protocol, one
LangChain OpenAI-compatible Chat Completions adapter, purpose-based `regular`
and `fast` model slots, native structured tool calls, normalized `LLMUsage`, and `Decimal`
cost with explicit provenance — provider payloads never leak past
`agentscope.models`. There is still **no runnable agent**; that remains a
separate, later axis. See `docs/plans/phase-1a.2-model-usage-cost.md`,
`src/agentscope/models/README.md`, `docs/adr/0012`–`0014`, and
`AgentScope_Phase0_Foundation_System_Design_v2.md`,
`AgentScope_Phase1A1_Concrete_SandboxRuntime_Implementation_Plan.md`,
`ARCHITECTURE.md`, `THREAT_MODEL.md`, `src/agentscope/runtime/README.md`,
`docs/findings/sbx-cli.md`, and `docs/adr/`.

## Supported environment

- **Python 3.14** is the target and the only version CI runs
  (`.python-version`, `requires-python = ">=3.14"`).
- Environment and dependencies are managed with [`uv`](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync                 # core + dev dependencies (includes the model stack: langchain, openai)
cp .env.example .env     # then fill in real secret values (never committed)
```

The model provider packages (`langchain`, `langchain-openai`, `langgraph`,
`openai`) are first-class runtime dependencies as of Phase 1A.2 — they are
imported lazily, so a model-free runtime configuration never loads them.

Optional dependency groups (declared and locked, not installed by default):

```bash
uv sync --extra future   # fastapi, streamlit, numpy, pandas
uv sync --extra phoenix  # arize-phoenix-otel convenience wrapper (pulls grpcio)
```

## Configuration

Configuration is split in two (design §8, ADR 0006):

- **Public** (`PublicConfig`) — non-secret, validated, serializable: selected
  architecture, typed `models.regular` and `models.fast` definitions, runtime mode, limits, telemetry
  endpoint, log level. Built programmatically or loaded from a typed TOML file
  via `agentscope.config.load_public_config(path)`. As of Phase 1A.2 it is a
  plain frozen model and is **not** an environment/`.env` source.
- **Secret** (`SecretConfig`) — credentials only, as `pydantic.SecretStr`
  (`openai_api_key`, `openrouter_api_key`, `meta_model_api_key`, `phoenix_api_key`,
  `otlp_headers`). Loaded from `.env` / `AGENTSCOPE_*`; consumed **only** by
  `agentscope.bootstrap`. Secret selection follows provider identity, not wire
  protocol.

`.env` is git-ignored and is now exclusively a local secret carrier;
`.env.example` lists variable names with safe placeholders.

## Tests

```bash
uv run pytest                       # deterministic suite (excludes external); prints coverage
uv run pytest --cov-report=html     # coverage HTML in htmlcov/
uv run pytest -m phoenix            # opt-in Phoenix smoke trace (needs endpoint + key env)
uv run pytest -m sbx                # opt-in real sbx (Docker Sandboxes) backend suite
uv run pytest -m openrouter         # opt-in OpenRouter live smoke (key from shell env or .env)
uv run pytest -m meta_model_api     # opt-in Meta Model API live smoke (key from shell env or .env)
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The deterministic suite needs no Docker, no Phoenix, and no model credentials.
`-m sbx` needs the `sbx` CLI installed and authenticated (`sbx login`) and a
global network policy already initialized — see
`docs/findings/sbx-cli.md`.

## Layout

```
src/agentscope/
  bootstrap/      composition root; only consumer of SecretConfig
  architectures/  AgentArchitecture contract, identity, registry
  config/         PublicConfig (+ TOML loader), SecretConfig
  models/         ModelAdapter protocol, request/response/usage/cost/identity,
                  registry, error taxonomy, OpenAI-compatible LangChain adapter (Phase 1A.2)
  runtime/        SandboxRuntime protocol, env allowlist, workspace path policy,
                  the sbx (Docker Sandboxes) backend (Phase 1A.1)
  telemetry/      TelemetrySink contract, Sanitizer, no-op/in-memory + Phoenix
tests/            unit / component / contract / external
docs/adr/         architecture decision records
```

# AgentScope

An experimental agent-design platform. AgentScope treats **agent topology as an
experimental variable** and the **harness (infrastructure + security
boundaries) as the stable platform**, so new agent architectures plug in without
rewriting shared infrastructure.

This repository is currently at **Phase 0 — Foundation**. Phase 0 builds only the
platform boundaries (configuration, the sandbox-runtime contract, telemetry,
security policy, the composition root, tests, docs). It ships **no runnable agent
behavior and no concrete sandbox backend**. See
`AgentScope_Phase0_Foundation_System_Design_v2.md`, `ARCHITECTURE.md`,
`THREAT_MODEL.md`, and `docs/adr/`.

## Supported environment

- **Python 3.14** is the primary target (`.python-version`). A **3.13**
  compatibility leg runs in CI (`requires-python = ">=3.13"`).
- Environment and dependencies are managed with [`uv`](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync                 # core + dev dependencies (fast; no grpc, no ML stack)
cp .env.example .env     # then fill in real secret values (never committed)
```

Optional dependency groups (declared and locked, not installed by default):

```bash
uv sync --extra future   # fastapi, streamlit, langchain, langgraph, openai, numpy, pandas
uv sync --extra phoenix  # arize-phoenix-otel convenience wrapper (pulls grpcio)
```

## Configuration

Configuration is split in two (design §8, ADR 0006):

- **Public** (`PublicConfig`) — non-secret, validated, serializable: selected
  architecture, `primary_model` (e.g. `openai:gpt-x`), runtime mode, limits,
  telemetry endpoint, log level.
- **Secret** (`SecretConfig`) — credentials only, as `pydantic.SecretStr`.
  Consumed **only** by `agentscope.bootstrap`.

All settings use the `AGENTSCOPE_` env prefix and may come from `.env` locally.
`.env` is git-ignored; `.env.example` lists variable names with safe
placeholders.

## Tests

```bash
uv run pytest                       # deterministic suite (excludes external); prints coverage
uv run pytest --cov-report=html     # coverage HTML in htmlcov/
uv run pytest -m phoenix            # opt-in Phoenix smoke trace (needs endpoint + key env)
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The deterministic suite needs no Docker, no Phoenix, and no model credentials.

## Layout

```
src/agentscope/
  bootstrap/      composition root; only consumer of SecretConfig
  architectures/  AgentArchitecture contract, identity, registry
  config/         PublicConfig, SecretConfig, model-identifier parsing
  runtime/        SandboxRuntime protocol, env allowlist, workspace path policy
  telemetry/      TelemetrySink contract, Sanitizer, no-op/in-memory + Phoenix
tests/            unit / component / contract / external
docs/adr/         architecture decision records
```

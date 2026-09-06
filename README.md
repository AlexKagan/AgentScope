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
timeout guarantees verified against the real sandbox, not just fakes. There
is still **no runnable agent**; that remains a separate, later axis. See
`AgentScope_Phase0_Foundation_System_Design_v2.md`,
`AgentScope_Phase1A1_Concrete_SandboxRuntime_Implementation_Plan.md`,
`ARCHITECTURE.md`, `THREAT_MODEL.md`, `src/agentscope/runtime/README.md`,
`docs/findings/sbx-cli.md`, and `docs/adr/`.

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
uv run pytest -m sbx                # opt-in real sbx (Docker Sandboxes) backend suite
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
  config/         PublicConfig, SecretConfig, model-identifier parsing
  runtime/        SandboxRuntime protocol, env allowlist, workspace path policy,
                  the sbx (Docker Sandboxes) backend (Phase 1A.1)
  telemetry/      TelemetrySink contract, Sanitizer, no-op/in-memory + Phoenix
tests/            unit / component / contract / external
docs/adr/         architecture decision records
```

# ADR 0001 — Tooling and Python version

## Status
Accepted (Phase 0).

## Context
We need one reproducible way to manage the environment, and a target Python
version. The v2 design doc suggested Python 3.13 primary with 3.14 compatibility
CI. The project owner has since decided 3.14 is the primary development target.

## Decision
- Use **`uv`** for environment, dependency resolution, and locking (`uv.lock`
  committed; `uv sync --frozen` in CI).
- **Python 3.14 is the primary/canonical version** (`.python-version = 3.14`).
- `requires-python = ">=3.13"` so a **3.13 compatibility leg** can still resolve
  and run in CI. CI runs the deterministic suite on both 3.14 and 3.13.
- `ruff` (lint + format) and `mypy --strict` are the quality gates.
- Later-phase heavy dependencies (`fastapi`, `streamlit`, `langchain`,
  `langgraph`, `openai`, `numpy`, `pandas`, `bottleneck`) are declared under the
  `future` optional-dependencies extra: locked now, not installed by default,
  never imported by Phase 0 code.

## Consequences
- Fast, reproducible default `uv sync`; the deterministic suite depends only on
  `pydantic`, `pydantic-settings`, and the pure-Python OpenTelemetry stack.
- If a `future` dependency lacks a 3.14 wheel, only `uv sync --extra future` is
  affected, not Phase 0.
- Inverting the design doc's version preference is recorded here deliberately.

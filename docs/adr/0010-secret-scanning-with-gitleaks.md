# ADR 0010 — Secret scanning with gitleaks

## Status
Accepted (Phase 0).

## Context
`.gitignore` + `.env.example` discipline prevents the obvious accidental commit,
but not a secret pasted into a source file, a test fixture, or a notebook.

## Decision
Run **gitleaks** as:
- a `pre-commit` hook (`.pre-commit-config.yaml`), and
- a step in the deterministic CI workflow.

`.env` and `.env.*` are git-ignored; `.env.example` is explicitly not ignored
and contains only placeholders. `tests/unit/test_repo_hygiene.py` asserts all of
this, plus that no `.env` is tracked.

## Consequences
- Contributors need `pre-commit install` once; CI enforces regardless.
- If gitleaks proves noisy, tune `.gitleaks.toml`; do not silently drop the CI
  step without updating this ADR.

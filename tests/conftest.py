"""Shared fixtures and fakes for the AgentScope Phase 0 test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# The literal fake secret values seeded into the environment by ``seeded_secret_env``.
# Downstream tests assert these substrings never appear in dumps, reprs, logs, or traces.
FAKE_OPENAI_KEY = "sk-FAKE-DEADBEEF-0000000000000000"
FAKE_PHOENIX_KEY = "phx-FAKE-1111111111111111"
FAKE_OTLP_HEADERS = "authorization=Bearer sk-FAKE-2222222222222222"


@pytest.fixture(autouse=True)
def clean_agentscope_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any ``AGENTSCOPE_*`` variables so tests are hermetic."""
    for key in list(os.environ):
        if key.startswith("AGENTSCOPE_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def seeded_secret_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Seed fake secrets into the environment and return the literal values."""
    values = {
        "AGENTSCOPE_OPENAI_API_KEY": FAKE_OPENAI_KEY,
        "AGENTSCOPE_PHOENIX_API_KEY": FAKE_PHOENIX_KEY,
        "AGENTSCOPE_OTLP_HEADERS": FAKE_OTLP_HEADERS,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture
def all_fake_secrets() -> tuple[str, ...]:
    """Every seeded fake secret substring, for absence assertions."""
    return (FAKE_OPENAI_KEY, FAKE_PHOENIX_KEY, FAKE_OTLP_HEADERS)


@pytest.fixture
def fake_workspace(tmp_path: os.PathLike[str]) -> Iterator[object]:
    """A real, empty workspace directory wrapped as a ``WorkspaceRoot``."""
    from pathlib import Path

    from agentscope.runtime.workspace import WorkspaceRoot

    ws = Path(tmp_path) / "ws"
    ws.mkdir()
    yield WorkspaceRoot(path=ws)

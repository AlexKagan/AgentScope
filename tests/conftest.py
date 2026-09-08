"""Shared fixtures and fakes for the AgentScope Phase 0 test suite."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from functools import cache

import pytest

from tests.external._sbx_baseline import EXPECTED_SBX_VERSION

# The literal fake secret values seeded into the environment by ``seeded_secret_env``.
# Downstream tests assert these substrings never appear in dumps, reprs, logs, or traces.
FAKE_OPENAI_KEY = "sk-FAKE-DEADBEEF-0000000000000000"
FAKE_PHOENIX_KEY = "phx-FAKE-1111111111111111"
FAKE_OTLP_HEADERS = "authorization=Bearer sk-FAKE-2222222222222222"
FAKE_OPENROUTER_KEY = "sk-or-FAKE-3333333333333333"
FAKE_META_MODEL_KEY = "sk-FAKE-META-4444444444444444"


@cache
def _verify_sbx_version() -> None:
    if os.environ.get("SBX_ALLOW_UNVERIFIED_VERSION") == "1":
        return
    completed = subprocess.run(
        ["sbx", "version"], capture_output=True, text=True, timeout=15, check=True
    )
    actual = completed.stdout.split()[2]
    if actual != EXPECTED_SBX_VERSION:
        raise RuntimeError(
            f"sbx version mismatch: expected {EXPECTED_SBX_VERSION}, got {actual}; "
            "set SBX_ALLOW_UNVERIFIED_VERSION=1 only for exploratory local testing"
        )


@pytest.fixture(autouse=True)
def enforce_sbx_test_baseline(request: pytest.FixtureRequest) -> None:
    """Fail real-sandbox tests fast when local CLI assumptions have drifted."""
    if request.node.get_closest_marker("sbx") is not None:
        _verify_sbx_version()


@pytest.fixture(autouse=True)
def clean_agentscope_env(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Remove any ``AGENTSCOPE_*`` variables so tests are hermetic.

    ``external``-marked tests are exempt: they legitimately talk to a real
    service and need the operator's real ``AGENTSCOPE_*`` configuration (API
    keys, endpoints) to reach them.
    """
    if request.node.get_closest_marker("external") is not None:
        return
    for key in list(os.environ):
        if key.startswith("AGENTSCOPE_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def seeded_secret_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Seed fake secrets into the environment and return the literal values."""
    values = {
        "AGENTSCOPE_OPENAI_API_KEY": FAKE_OPENAI_KEY,
        "AGENTSCOPE_OPENROUTER_API_KEY": FAKE_OPENROUTER_KEY,
        "AGENTSCOPE_META_MODEL_API_KEY": FAKE_META_MODEL_KEY,
        "AGENTSCOPE_PHOENIX_API_KEY": FAKE_PHOENIX_KEY,
        "AGENTSCOPE_OTLP_HEADERS": FAKE_OTLP_HEADERS,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture
def all_fake_secrets() -> tuple[str, ...]:
    """Every seeded fake secret substring, for absence assertions."""
    return (
        FAKE_OPENAI_KEY,
        FAKE_OPENROUTER_KEY,
        FAKE_META_MODEL_KEY,
        FAKE_PHOENIX_KEY,
        FAKE_OTLP_HEADERS,
    )


@pytest.fixture
def fake_workspace(tmp_path: os.PathLike[str]) -> Iterator[object]:
    """A real, empty workspace directory wrapped as a ``WorkspaceRoot``."""
    from pathlib import Path

    from agentscope.runtime.workspace import WorkspaceRoot

    ws = Path(tmp_path) / "ws"
    ws.mkdir()
    yield WorkspaceRoot(path=ws)

"""Component test: platform starts with no creds and no heavy imports (design 13.2)."""

from __future__ import annotations

import sys

from agentscope.bootstrap.composition import build_platform
from agentscope.config.public import PublicConfig
from agentscope.config.secret import SecretConfig
from agentscope.telemetry.noop import NoOpSink

_HEAVY = ("openai", "phoenix", "opentelemetry", "langchain", "langgraph", "streamlit", "fastapi")


def test_starts_with_telemetry_disabled_and_no_model() -> None:
    platform = build_platform(
        PublicConfig(_env_file=None),  # type: ignore[call-arg]
        SecretConfig(_env_file=None),  # type: ignore[call-arg]
    )
    assert isinstance(platform.telemetry, NoOpSink)
    assert platform.model_client is None


def test_default_build_does_not_import_heavy_dependencies() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in _HEAVY:
            del sys.modules[name]
    build_platform(
        PublicConfig(_env_file=None),  # type: ignore[call-arg]
        SecretConfig(_env_file=None),  # type: ignore[call-arg]
    )
    leaked = sorted({n.split(".")[0] for n in sys.modules if n.split(".")[0] in _HEAVY})
    assert leaked == []

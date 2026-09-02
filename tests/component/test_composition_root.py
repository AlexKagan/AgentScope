"""Component tests for the composition root (design 13.2)."""

from __future__ import annotations

import pytest

from agentscope.bootstrap.composition import build_platform
from agentscope.config.models import ModelIdentifier
from agentscope.config.public import PublicConfig
from agentscope.config.secret import MissingSecretError, SecretConfig
from agentscope.telemetry.memory import InMemorySink
from agentscope.telemetry.noop import NoOpSink
from tests._fakes import FakeModelClientFactory


def _public(**kw: object) -> PublicConfig:
    return PublicConfig(_env_file=None, **kw)  # type: ignore[arg-type]


def _secret(**kw: object) -> SecretConfig:
    return SecretConfig(_env_file=None, **kw)  # type: ignore[arg-type]


def test_defaults_build_without_credentials_or_network() -> None:
    platform = build_platform(_public(), _secret())
    assert isinstance(platform.telemetry, NoOpSink)
    assert platform.model_client is None
    assert len(platform.registry) == 0


def test_injected_telemetry_factory_is_used() -> None:
    sink = InMemorySink()
    platform = build_platform(
        _public(telemetry_enabled=True, telemetry_endpoint="http://x/v1/traces"),
        _secret(),
        telemetry_factory=lambda _p, _s: sink,
    )
    assert platform.telemetry is sink


def test_model_client_built_from_key_via_factory() -> None:
    factory = FakeModelClientFactory()
    platform = build_platform(
        _public(primary_model="openai:gpt-x"),
        _secret(openai_api_key="sk-REAL-VALUE-123"),
        model_client_factory=factory,
    )
    assert factory.calls == [(ModelIdentifier("openai", "gpt-x"), "sk-REAL-VALUE-123")]
    assert platform.model_client is factory.client


def test_missing_key_fails_fast_at_bootstrap() -> None:
    with pytest.raises(MissingSecretError):
        build_platform(
            _public(primary_model="openai:gpt-x"),
            _secret(),
            model_client_factory=FakeModelClientFactory(),
        )

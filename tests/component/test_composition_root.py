"""Component tests for the composition root (design 13.2)."""

from __future__ import annotations

import pytest

from agentscope.bootstrap.composition import build_platform
from agentscope.config.public import PublicConfig
from agentscope.config.secret import MissingSecretError, SecretConfig
from agentscope.models.configuration import ModelDefinition
from agentscope.telemetry.memory import InMemorySink
from agentscope.telemetry.noop import NoOpSink
from tests._fakes import FakeModelAdapterFactory

_META = ModelDefinition(
    key="primary-reasoner",
    provider="meta",
    model_name="muse-spark-1.3",
    credential_ref="meta_model_api_key",
)
_OPENROUTER = ModelDefinition(
    key="router",
    provider="openrouter",
    model_name="some/cheap-model",
    credential_ref="openrouter_api_key",
)


def _public(**kw: object) -> PublicConfig:
    return PublicConfig(**kw)  # type: ignore[arg-type]


def _secret(**kw: object) -> SecretConfig:
    return SecretConfig(_env_file=None, **kw)  # type: ignore[arg-type]


def test_defaults_build_without_credentials_or_network() -> None:
    platform = build_platform(_public(), _secret())
    assert isinstance(platform.telemetry, NoOpSink)
    assert len(platform.models) == 0
    assert len(platform.registry) == 0


def test_injected_telemetry_factory_is_used() -> None:
    sink = InMemorySink()
    platform = build_platform(
        _public(telemetry_enabled=True, telemetry_endpoint="http://x/v1/traces"),
        _secret(),
        telemetry_factory=lambda _p, _s: sink,
    )
    assert platform.telemetry is sink


def test_model_adapter_built_from_key_and_registered() -> None:
    factory = FakeModelAdapterFactory()
    platform = build_platform(
        _public(primary_model_key="primary-reasoner", models={"primary-reasoner": _META}),
        _secret(meta_model_api_key="sk-REAL-META-123"),
        model_adapter_factory=factory,
    )
    assert factory.calls == [(_META, "sk-REAL-META-123")]
    resolved = platform.models.resolve("primary-reasoner")
    assert resolved.definition is _META
    assert resolved.adapter is factory.adapters[0]


def test_meta_selection_does_not_require_openrouter_or_openai_key() -> None:
    build_platform(
        _public(primary_model_key="primary-reasoner", models={"primary-reasoner": _META}),
        _secret(meta_model_api_key="sk-REAL-META-123"),
        model_adapter_factory=FakeModelAdapterFactory(),
    )  # no openai/openrouter key present -> still succeeds


def test_openrouter_selection_requires_only_openrouter_key() -> None:
    build_platform(
        _public(primary_model_key="router", models={"router": _OPENROUTER}),
        _secret(openrouter_api_key="sk-or-REAL-123"),
        model_adapter_factory=FakeModelAdapterFactory(),
    )


def test_missing_key_fails_fast_at_bootstrap() -> None:
    with pytest.raises(MissingSecretError):
        build_platform(
            _public(primary_model_key="primary-reasoner", models={"primary-reasoner": _META}),
            _secret(),
            model_adapter_factory=FakeModelAdapterFactory(),
        )

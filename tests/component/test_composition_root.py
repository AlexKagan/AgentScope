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
    key="regular", provider="meta", model_name="muse-spark-1.3", credential_ref="meta_model_api_key"
)
_OPENROUTER = ModelDefinition(
    key="fast",
    provider="openrouter",
    model_name="some/cheap-model",
    credential_ref="openrouter_api_key",
)


def _public(**kw: object) -> PublicConfig:
    return PublicConfig(**kw)  # type: ignore[arg-type]


def _secret(**kw: object) -> SecretConfig:
    return SecretConfig(_env_file=None, **kw)  # type: ignore[arg-type]


def _configured() -> PublicConfig:
    return _public(models={"regular": _META, "fast": _OPENROUTER})


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


def test_both_purpose_slots_are_built_and_registered() -> None:
    factory = FakeModelAdapterFactory()
    platform = build_platform(
        _configured(),
        _secret(meta_model_api_key="sk-REAL-META-123", openrouter_api_key="sk-or-REAL-123"),
        model_adapter_factory=factory,
    )
    assert factory.calls == [(_META, "sk-REAL-META-123"), (_OPENROUTER, "sk-or-REAL-123")]
    assert platform.models.resolve("regular").definition is _META
    assert platform.models.resolve("fast").definition is _OPENROUTER
    assert platform.models.keys() == ("fast", "regular")


@pytest.mark.parametrize(
    "secrets",
    [
        {"meta_model_api_key": "sk-REAL-META-123"},
        {"openrouter_api_key": "sk-or-REAL-123"},
    ],
)
def test_each_configured_slot_requires_its_credential(secrets: dict[str, str]) -> None:
    with pytest.raises(MissingSecretError):
        build_platform(
            _configured(), _secret(**secrets), model_adapter_factory=FakeModelAdapterFactory()
        )


def test_same_provider_for_both_slots_reuses_credential_without_aliases() -> None:
    fast_meta = _META.model_copy(update={"key": "fast", "model_name": "muse-spark-1.3-fast"})
    factory = FakeModelAdapterFactory()
    platform = build_platform(
        _public(models={"regular": _META, "fast": fast_meta}),
        _secret(meta_model_api_key="sk-REAL-META-123"),
        model_adapter_factory=factory,
    )
    assert len(factory.calls) == 2
    assert platform.models.keys() == ("fast", "regular")

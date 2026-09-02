"""Unit tests for PublicConfig (design 8.1, 13.1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agentscope.config.models import ModelIdentifier
from agentscope.config.public import PublicConfig, RuntimeMode


def _cfg(**overrides: object) -> PublicConfig:
    return PublicConfig(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_defaults() -> None:
    cfg = _cfg()
    assert cfg.runtime_mode is RuntimeMode.FAKE
    assert cfg.telemetry_enabled is False
    assert cfg.log_level == "INFO"
    assert cfg.limits.default_timeout_s == 30.0
    assert cfg.model_identifier is None


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_PRIMARY_MODEL", "openai:gpt-x")
    monkeypatch.setenv("AGENTSCOPE_LOG_LEVEL", "debug")
    cfg = PublicConfig(_env_file=None)  # type: ignore[call-arg]
    assert cfg.model_identifier == ModelIdentifier("openai", "gpt-x")
    assert cfg.log_level == "DEBUG"


@pytest.mark.parametrize("bad", ["chatty", "trace", ""])
def test_rejects_unknown_log_level(bad: str) -> None:
    with pytest.raises(ValidationError):
        _cfg(log_level=bad)


def test_rejects_non_positive_limits() -> None:
    with pytest.raises(ValidationError):
        _cfg(limits={"default_timeout_s": 0})
    with pytest.raises(ValidationError):
        _cfg(limits={"max_output_bytes": -1})


def test_rejects_bad_model_identifier() -> None:
    with pytest.raises(ValidationError):
        _cfg(primary_model="not-a-model-id")


def test_telemetry_endpoint_required_when_enabled() -> None:
    with pytest.raises(ValidationError):
        _cfg(telemetry_enabled=True)
    ok = _cfg(telemetry_enabled=True, telemetry_endpoint="http://localhost:6006/v1/traces")
    assert ok.telemetry_enabled is True


def test_safe_dump_is_json_roundtrippable() -> None:
    cfg = _cfg(primary_model="openai:gpt-x")
    dumped = cfg.safe_dump()
    assert json.loads(json.dumps(dumped))["primary_model"] == "openai:gpt-x"


def test_public_config_ignores_secret_environment(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    cfg = PublicConfig()  # type: ignore[call-arg]  # picks up real env, not _env_file
    blob = repr(cfg) + json.dumps(cfg.safe_dump())
    for secret in all_fake_secrets:
        assert secret not in blob
    assert not hasattr(cfg, "openai_api_key")


def test_frozen() -> None:
    cfg = _cfg()
    with pytest.raises(ValidationError):
        cfg.log_level = "DEBUG"  # type: ignore[misc]

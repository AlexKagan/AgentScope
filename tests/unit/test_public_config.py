"""Unit tests for PublicConfig and its TOML loader (design 8.1, 13.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentscope.config.loader import load_public_config
from agentscope.config.public import PublicConfig, RuntimeMode
from agentscope.models.configuration import ModelDefinition

_META_MODEL = {
    "key": "primary-reasoner",
    "provider": "meta",
    "model_name": "muse-spark-1.3",
    "credential_ref": "meta_model_api_key",
}


def test_defaults() -> None:
    cfg = PublicConfig()
    assert cfg.runtime_mode is RuntimeMode.FAKE
    assert cfg.telemetry_enabled is False
    assert cfg.log_level == "INFO"
    assert cfg.limits.default_timeout_s == 30.0
    assert cfg.models == {}
    assert cfg.primary_model is None


def test_is_not_a_settings_source_and_ignores_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTSCOPE_LOG_LEVEL", "debug")
    monkeypatch.setenv("AGENTSCOPE_PRIMARY_MODEL_KEY", "primary-reasoner")
    cfg = PublicConfig()
    assert cfg.log_level == "INFO"
    assert cfg.primary_model_key is None


@pytest.mark.parametrize("bad", ["chatty", "trace", ""])
def test_rejects_unknown_log_level(bad: str) -> None:
    with pytest.raises(ValidationError):
        PublicConfig(log_level=bad)


def test_rejects_non_positive_limits() -> None:
    with pytest.raises(ValidationError):
        PublicConfig(limits={"default_timeout_s": 0})  # type: ignore[arg-type]


def test_telemetry_endpoint_required_when_enabled() -> None:
    with pytest.raises(ValidationError):
        PublicConfig(telemetry_enabled=True)
    ok = PublicConfig(telemetry_enabled=True, telemetry_endpoint="http://localhost:6006/v1/traces")
    assert ok.telemetry_enabled is True


def test_model_catalog_key_must_match_definition_key() -> None:
    defn = ModelDefinition(**_META_MODEL)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        PublicConfig(models={"wrong-key": defn})


def test_primary_model_key_must_be_in_catalog() -> None:
    with pytest.raises(ValidationError):
        PublicConfig(primary_model_key="ghost")


def test_primary_model_resolves_to_definition() -> None:
    cfg = PublicConfig(
        primary_model_key="primary-reasoner",
        models={"primary-reasoner": ModelDefinition(**_META_MODEL)},  # type: ignore[arg-type]
    )
    assert cfg.primary_model is not None
    assert cfg.primary_model.model_name == "muse-spark-1.3"


def test_safe_dump_is_json_roundtrippable() -> None:
    cfg = PublicConfig(
        primary_model_key="primary-reasoner",
        models={"primary-reasoner": ModelDefinition(**_META_MODEL)},  # type: ignore[arg-type]
    )
    dumped = cfg.safe_dump()
    round_tripped = json.loads(json.dumps(dumped))
    assert round_tripped["primary_model_key"] == "primary-reasoner"
    assert round_tripped["models"]["primary-reasoner"]["model_name"] == "muse-spark-1.3"


def test_frozen() -> None:
    cfg = PublicConfig()
    with pytest.raises(ValidationError):
        cfg.log_level = "DEBUG"  # type: ignore[misc]


def test_loader_reads_toml(tmp_path: Path) -> None:
    path = tmp_path / "agentscope.toml"
    path.write_text(
        "\n".join(
            [
                'primary_model_key = "primary-reasoner"',
                'log_level = "debug"',
                "",
                "[models.primary-reasoner]",
                'provider = "meta"',
                'model_name = "muse-spark-1.3"',
                'credential_ref = "meta_model_api_key"',
                "timeout_s = 45",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_public_config(path)
    assert cfg.log_level == "DEBUG"
    assert cfg.primary_model is not None
    assert cfg.primary_model.timeout_s == 45.0


def test_loader_rejects_invalid_config(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('primary_model_key = "missing"\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_public_config(path)

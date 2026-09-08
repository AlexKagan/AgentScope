"""Unit tests for PublicConfig and its TOML loader (design 8.1, 13.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentscope.config.loader import load_public_config
from agentscope.config.public import PublicConfig, RuntimeMode

_META_MODEL = {
    "provider": "meta",
    "model_name": "muse-spark-1.3",
    "credential_ref": "meta_model_api_key",
}
_ROUTER_MODEL = {
    "provider": "openrouter",
    "model_name": "openai/gpt-4o-mini",
    "credential_ref": "openrouter_api_key",
}


def _models() -> dict[str, object]:
    return {"regular": _META_MODEL, "fast": _ROUTER_MODEL}


def test_defaults_are_model_free() -> None:
    cfg = PublicConfig()
    assert cfg.runtime_mode is RuntimeMode.FAKE
    assert cfg.telemetry_enabled is False
    assert cfg.log_level == "INFO"
    assert cfg.limits.default_timeout_s == 30.0
    assert cfg.models is None


def test_is_not_a_settings_source_and_ignores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_LOG_LEVEL", "debug")
    cfg = PublicConfig()
    assert cfg.log_level == "INFO"


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


@pytest.mark.parametrize("models", [{"regular": _META_MODEL}, {"fast": _ROUTER_MODEL}])
def test_model_enabled_config_requires_both_slots(models: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PublicConfig(models=models)  # type: ignore[arg-type]


def test_only_regular_and_fast_slots_are_allowed() -> None:
    with pytest.raises(ValidationError):
        PublicConfig(models={**_models(), "meta-fast": _META_MODEL})  # type: ignore[arg-type]


def test_slots_receive_fixed_internal_keys() -> None:
    cfg = PublicConfig(models=_models())  # type: ignore[arg-type]
    assert cfg.models is not None
    assert cfg.models.regular.key == "regular"
    assert cfg.models.fast.key == "fast"


def test_legacy_primary_model_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PublicConfig(primary_model_key="primary-reasoner")  # type: ignore[call-arg]


def test_public_slot_rejects_user_supplied_internal_key() -> None:
    with pytest.raises(ValidationError, match="must not contain an internal key"):
        PublicConfig.model_validate(
            {
                "models": {
                    "regular": {**_META_MODEL, "key": "regular"},
                    "fast": _ROUTER_MODEL,
                }
            }
        )


def test_safe_dump_is_json_roundtrippable() -> None:
    cfg = PublicConfig(models=_models())  # type: ignore[arg-type]
    round_tripped = json.loads(json.dumps(cfg.safe_dump()))
    assert "primary_model_key" not in round_tripped
    assert round_tripped["models"]["regular"]["model_name"] == "muse-spark-1.3"


def test_frozen() -> None:
    cfg = PublicConfig()
    with pytest.raises(ValidationError):
        cfg.log_level = "DEBUG"  # type: ignore[misc]


def test_loader_reads_canonical_toml_and_preserves_omission(tmp_path: Path) -> None:
    path = tmp_path / "agentscope.toml"
    path.write_text(
        """log_level = "debug"

[models.regular]
provider = "openrouter"
model_name = "anthropic/claude-sonnet-4.6"
credential_ref = "openrouter_api_key"
capabilities = ["text", "tool_calling", "reasoning"]

[models.regular.parameters]
temperature = 0.0
verbosity = "high"

[models.regular.reasoning]
mode = "enabled"
effort = "high"

[models.fast]
provider = "meta"
model_name = "muse-spark-1.3"
credential_ref = "meta_model_api_key"

""",
        encoding="utf-8",
    )
    cfg = load_public_config(path)
    assert cfg.log_level == "DEBUG"
    assert cfg.models is not None
    assert cfg.models.regular.parameters.verbosity == "high"
    assert "max_output_tokens" not in cfg.models.regular.parameters.supplied()
    assert cfg.models.fast.reasoning.mode == "provider_default"


def test_loader_rejects_legacy_config(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('primary_model_key = "missing"\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_public_config(path)

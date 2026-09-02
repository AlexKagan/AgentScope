"""Unit tests for SecretConfig secret isolation (design 8.4, 8.7, 13.1)."""

from __future__ import annotations

import pytest

from agentscope.config.secret import MissingSecretError, SecretConfig


def test_unset_fields_are_none() -> None:
    cfg = SecretConfig(_env_file=None)  # type: ignore[call-arg]
    assert cfg.openai_api_key is None
    assert cfg.phoenix_api_key is None
    assert cfg.otlp_headers is None


def test_loads_secretstr_from_env(seeded_secret_env: dict[str, str]) -> None:
    cfg = SecretConfig()  # type: ignore[call-arg]
    assert cfg.openai_api_key is not None
    assert cfg.openai_api_key.get_secret_value() == seeded_secret_env["AGENTSCOPE_OPENAI_API_KEY"]


def test_no_secret_leaks_in_any_representation(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    cfg = SecretConfig()  # type: ignore[call-arg]
    surfaces = [
        repr(cfg),
        str(cfg),
        f"{cfg}",
        str(cfg.model_dump()),
        cfg.model_dump_json(),
        str(cfg.safe_dump()),
    ]
    for surface in surfaces:
        for secret in all_fake_secrets:
            assert secret not in surface


def test_safe_dump_lists_configured_fields(seeded_secret_env: dict[str, str]) -> None:
    cfg = SecretConfig()  # type: ignore[call-arg]
    assert cfg.safe_dump() == {
        "openai_api_key": "REDACTED",
        "phoenix_api_key": "REDACTED",
        "otlp_headers": "REDACTED",
    }


def test_safe_dump_empty_when_nothing_configured() -> None:
    # clean_agentscope_env (autouse) has already stripped AGENTSCOPE_* vars.
    assert SecretConfig(_env_file=None).safe_dump() == {}  # type: ignore[call-arg]


def test_require_returns_value_when_set(seeded_secret_env: dict[str, str]) -> None:
    cfg = SecretConfig()  # type: ignore[call-arg]
    assert cfg.require("openai_api_key") == seeded_secret_env["AGENTSCOPE_OPENAI_API_KEY"]


def test_require_raises_without_value_and_message_has_no_secret() -> None:
    cfg = SecretConfig(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(MissingSecretError) as excinfo:
        cfg.require("openai_api_key")
    assert "openai_api_key" in str(excinfo.value)


def test_require_rejects_unknown_field() -> None:
    cfg = SecretConfig(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(MissingSecretError):
        cfg.require("not_a_field")

"""Unit tests for public model-identifier parsing (design 8.1, 13.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agentscope.config.models import ModelIdentifier, parse_model_identifier


def test_parses_provider_and_name() -> None:
    mid = parse_model_identifier("openai:gpt-x")
    assert mid == ModelIdentifier(provider="openai", name="gpt-x")
    assert str(mid) == "openai:gpt-x"


@pytest.mark.parametrize(
    "value",
    [
        "openai",  # no colon
        "openai:gpt:x",  # extra colon
        ":gpt-x",  # empty provider
        "openai:",  # empty name
        "",  # empty
    ],
)
def test_rejects_malformed(value: str) -> None:
    with pytest.raises(ValueError):
        parse_model_identifier(value)


@pytest.mark.parametrize(
    "value",
    [
        "openai: gpt-x",  # whitespace
        " openai:gpt-x",
        "openai:gpt-x\n",
        "openai:sk-abcdefghijklmnop1234567890",
        "provider:abcdefghijklmnopqrstuvwxyz0123456789",
    ],
)
def test_rejects_credential_looking_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_model_identifier(value)


def test_identifier_is_frozen() -> None:
    mid = parse_model_identifier("openai:gpt-x")
    with pytest.raises(FrozenInstanceError):
        mid.provider = "anthropic"  # type: ignore[misc]

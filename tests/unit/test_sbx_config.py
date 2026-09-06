"""Unit tests for ``SbxRuntimeConfig`` (Phase 1A.1, Step 2).

Values here are constrained by empirically observed ``sbx`` CLI behavior -
see ``docs/findings/sbx-cli.md`` (1 GiB memory minimum, sandbox name rules).
"""

from __future__ import annotations

import dataclasses

import pytest

from agentscope.runtime.errors import RuntimeContractError
from agentscope.runtime.sbx import NetworkPolicy, SbxRuntimeConfig


def test_default_config_is_valid_and_safe() -> None:
    config = SbxRuntimeConfig()
    assert config.cpu_limit >= 1
    assert config.network_policy is NetworkPolicy.DISABLED
    assert config.create_timeout_s > 0
    assert config.default_command_timeout_s > 0
    assert config.cleanup_timeout_s > 0


def test_sbx_config_defaults_network_disabled() -> None:
    assert SbxRuntimeConfig().network_policy is NetworkPolicy.DISABLED


@pytest.mark.parametrize("cpu_limit", [0, -1, -100])
def test_sbx_config_rejects_nonpositive_cpu(cpu_limit: int) -> None:
    with pytest.raises(RuntimeContractError):
        SbxRuntimeConfig(cpu_limit=cpu_limit)


@pytest.mark.parametrize(
    "memory_limit",
    [
        "512m",  # below the empirically observed 1 GiB sbx minimum
        "0g",
        "-1g",
        "1024",  # missing unit suffix
        "1gb",  # sbx expects a single-letter unit, not "gb"
        "",
        "abc",
    ],
)
def test_sbx_config_rejects_invalid_memory(memory_limit: str) -> None:
    with pytest.raises(RuntimeContractError):
        SbxRuntimeConfig(memory_limit=memory_limit)


@pytest.mark.parametrize("memory_limit", ["1g", "1024m", "2G", "1536M", "8g"])
def test_sbx_config_accepts_valid_memory_at_or_above_minimum(memory_limit: str) -> None:
    config = SbxRuntimeConfig(memory_limit=memory_limit)
    assert config.memory_limit == memory_limit


@pytest.mark.parametrize(
    "field, value",
    [
        ("create_timeout_s", 0),
        ("create_timeout_s", -1),
        ("default_command_timeout_s", 0),
        ("default_command_timeout_s", -1),
        ("cleanup_timeout_s", 0),
        ("cleanup_timeout_s", -1),
    ],
)
def test_sbx_config_rejects_invalid_timeout(field: str, value: float) -> None:
    with pytest.raises(RuntimeContractError):
        SbxRuntimeConfig(**{field: value})


@pytest.mark.parametrize(
    "name_prefix",
    [
        "a",  # too short (< 2 chars)
        "-abc",  # must start with letter/number
        ".abc",  # must start with letter/number
        "ab_cd",  # underscore not allowed
        "ab cd",  # space not allowed
        "default",  # reserved name
    ],
)
def test_sbx_config_rejects_invalid_sandbox_name_prefix(name_prefix: str) -> None:
    with pytest.raises(RuntimeContractError):
        SbxRuntimeConfig(sandbox_name_prefix=name_prefix)


@pytest.mark.parametrize("name_prefix", ["ab", "agentscope", "agent-scope.run1"])
def test_sbx_config_accepts_valid_sandbox_name_prefix(name_prefix: str) -> None:
    assert SbxRuntimeConfig(sandbox_name_prefix=name_prefix).sandbox_name_prefix == name_prefix


def test_sbx_config_does_not_contain_credentials() -> None:
    # No field name should suggest a secret/credential lives on this config -
    # SbxRuntimeConfig is resource/policy shape only, never secret material.
    field_names = {f.name for f in dataclasses.fields(SbxRuntimeConfig)}
    forbidden_substrings = ("key", "token", "secret", "password", "credential")
    for name in field_names:
        lowered = name.lower()
        assert not any(bad in lowered for bad in forbidden_substrings), name


def test_sbx_config_is_frozen() -> None:
    config = SbxRuntimeConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.cpu_limit = 4  # type: ignore[misc]

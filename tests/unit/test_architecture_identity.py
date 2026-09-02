"""Unit tests for ArchitectureIdentity (design 7, 13.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agentscope.architectures.identity import ArchitectureIdentity


def test_valid_identity() -> None:
    ident = ArchitectureIdentity("simple_tool_agent", "1.0.0")
    assert ident.architecture_key == "simple_tool_agent"
    assert ident.architecture_version == "1.0.0"


@pytest.mark.parametrize("key", ["Bad Key", "1abc", "", "has-dash", "UPPER", "_leading"])
def test_rejects_bad_key(key: str) -> None:
    with pytest.raises(ValueError):
        ArchitectureIdentity(key, "1.0.0")


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3.4", "1.2.x", ""])
def test_rejects_bad_version(version: str) -> None:
    with pytest.raises(ValueError):
        ArchitectureIdentity("simple_tool_agent", version)


def test_is_frozen() -> None:
    ident = ArchitectureIdentity("simple_tool_agent", "1.0.0")
    with pytest.raises(FrozenInstanceError):
        ident.architecture_key = "other"  # type: ignore[misc]

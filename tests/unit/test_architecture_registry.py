"""Unit tests for ArchitectureRegistry (design 6, 13.1)."""

from __future__ import annotations

import pytest

from agentscope.architectures.errors import (
    DuplicateArchitectureError,
    UnknownArchitectureError,
)
from agentscope.architectures.registry import ArchitectureRegistry
from tests._fakes import DummyArchitecture


def test_register_then_resolve_returns_same_object() -> None:
    reg = ArchitectureRegistry()
    arch = DummyArchitecture(key="alpha")
    reg.register(arch)
    assert reg.resolve("alpha") is arch


def test_duplicate_register_rejected() -> None:
    reg = ArchitectureRegistry()
    reg.register(DummyArchitecture(key="alpha"))
    with pytest.raises(DuplicateArchitectureError):
        reg.register(DummyArchitecture(key="alpha"))
    with pytest.raises(DuplicateArchitectureError):
        reg.register_factory("alpha", lambda: DummyArchitecture(key="alpha"))


def test_resolve_unknown_key_rejected() -> None:
    reg = ArchitectureRegistry()
    with pytest.raises(UnknownArchitectureError):
        reg.resolve("missing")


def test_factory_is_called_once_and_cached() -> None:
    reg = ArchitectureRegistry()
    calls = 0

    def factory() -> DummyArchitecture:
        nonlocal calls
        calls += 1
        return DummyArchitecture(key="beta")

    reg.register_factory("beta", factory)
    first = reg.resolve("beta")
    second = reg.resolve("beta")
    assert first is second
    assert calls == 1


def test_keys_are_sorted_regardless_of_insertion_order() -> None:
    reg = ArchitectureRegistry()
    for key in ("gamma", "alpha", "beta"):
        reg.register(DummyArchitecture(key=key))
    assert reg.keys() == ("alpha", "beta", "gamma")


def test_contains_and_len() -> None:
    reg = ArchitectureRegistry()
    assert len(reg) == 0
    reg.register(DummyArchitecture(key="alpha"))
    assert "alpha" in reg
    assert "nope" not in reg
    assert len(reg) == 1

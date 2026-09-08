"""Stable-key model registry (design 8.1)."""

from __future__ import annotations

import pytest

from agentscope.models.configuration import ModelDefinition
from agentscope.models.errors import ModelConfigurationError
from agentscope.models.identity import SafeModelIdentity
from agentscope.models.registry import ModelRegistry
from agentscope.models.requests import ModelRequest
from agentscope.models.responses import ModelResponse


def _defn(key: str = "primary-reasoner", **over: object) -> ModelDefinition:
    base: dict[str, object] = {
        "key": key,
        "provider": "meta",
        "model_name": "muse-spark-1.3",
        "credential_ref": "meta_model_api_key",
    }
    base.update(over)
    return ModelDefinition(**base)  # type: ignore[arg-type]


class _FakeAdapter:
    def __init__(self, identity: SafeModelIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> SafeModelIdentity:
        return self._identity

    async def ainvoke(self, request: ModelRequest) -> ModelResponse:  # pragma: no cover
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover
        return None


def test_register_and_resolve() -> None:
    reg = ModelRegistry()
    d = _defn()
    reg.register(d, _FakeAdapter(d.identity()))
    resolved = reg.resolve("primary-reasoner")
    assert resolved.definition is d
    assert reg.keys() == ("primary-reasoner",)
    assert "primary-reasoner" in reg
    assert len(reg) == 1


def test_duplicate_key_rejected() -> None:
    reg = ModelRegistry()
    d = _defn()
    reg.register(d, _FakeAdapter(d.identity()))
    with pytest.raises(ModelConfigurationError):
        reg.register(d, _FakeAdapter(d.identity()))


def test_unknown_key_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        ModelRegistry().resolve("nope")


def test_adapter_identity_mismatch_rejected() -> None:
    reg = ModelRegistry()
    d = _defn()
    other = _defn(model_name="different-model")
    with pytest.raises(ModelConfigurationError):
        reg.register(d, _FakeAdapter(other.identity()))

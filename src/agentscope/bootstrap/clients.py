"""Trusted client construction (design 8.3).

This is the seam where a raw credential becomes a narrow authenticated
capability. Phase 0 ships no model provider adapter, so the default factory
raises; tests inject a fake. Only :mod:`agentscope.bootstrap` calls this.
"""

from __future__ import annotations

from typing import Protocol

from agentscope.config.models import ModelIdentifier

__all__ = ["ModelClientFactory", "default_model_client_factory"]


class ModelClientFactory(Protocol):
    """Builds an authenticated model client from an identifier and a key."""

    def __call__(self, model: ModelIdentifier, api_key: str) -> object: ...


def default_model_client_factory(model: ModelIdentifier, api_key: str) -> object:
    """Phase 0 placeholder - model invocation arrives in Phase 1A."""
    raise NotImplementedError(
        "model invocation is not implemented in Phase 0 (arrives in Phase 1A); "
        "inject a model_client_factory to wire a client"
    )

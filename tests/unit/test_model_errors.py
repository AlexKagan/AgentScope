"""The normalized model-error taxonomy (design 7.6)."""

from __future__ import annotations

import pytest

from agentscope.models.errors import (
    ModelAuthenticationError,
    ModelAuthorizationError,
    ModelCapabilityError,
    ModelConfigurationError,
    ModelConnectionError,
    ModelError,
    ModelInvalidRequestError,
    ModelProviderError,
    ModelRateLimitError,
    ModelResponseNormalizationError,
    ModelTimeoutError,
)

_ALL = [
    ModelConfigurationError,
    ModelCapabilityError,
    ModelAuthenticationError,
    ModelAuthorizationError,
    ModelRateLimitError,
    ModelTimeoutError,
    ModelConnectionError,
    ModelInvalidRequestError,
    ModelProviderError,
    ModelResponseNormalizationError,
]


@pytest.mark.parametrize("cls", _ALL)
def test_every_category_is_a_model_error(cls: type[ModelError]) -> None:
    assert issubclass(cls, ModelError)


@pytest.mark.parametrize("cls", _ALL)
def test_categories_are_not_valueerror(cls: type[ModelError]) -> None:
    # They must propagate unwrapped out of pydantic validators.
    assert not issubclass(cls, ValueError)


def test_original_exception_is_chained() -> None:
    original = TimeoutError("socket timed out")
    try:
        raise ModelTimeoutError("provider attempt exceeded 60s") from original
    except ModelTimeoutError as exc:
        assert exc.__cause__ is original

"""Normalized model-error taxonomy (design 7.6).

Every provider or LangChain failure the adapter observes is translated into one
of these stable categories. The original exception is preserved as the chained
cause (``raise ModelX(...) from original``); it is never re-raised bare and the
adapter never retries.

Error messages and any attached safe metadata must not contain credentials,
authorization headers, complete request bodies, or raw provider responses.
"""

from __future__ import annotations

__all__ = [
    "ModelAuthenticationError",
    "ModelAuthorizationError",
    "ModelCapabilityError",
    "ModelConfigurationError",
    "ModelConnectionError",
    "ModelError",
    "ModelInvalidRequestError",
    "ModelProviderError",
    "ModelRateLimitError",
    "ModelResponseNormalizationError",
    "ModelTimeoutError",
]


class ModelError(Exception):
    """Base class for every normalized model-boundary failure."""


class ModelConfigurationError(ModelError):
    """A model definition, registry, or endpoint is invalid or unknown.

    Raised during composition/validation, before any provider I/O.
    """


class ModelCapabilityError(ModelError):
    """The request needs a capability the selected model did not declare."""


class ModelAuthenticationError(ModelError):
    """The provider rejected the supplied credential (HTTP 401 or equivalent)."""


class ModelAuthorizationError(ModelError):
    """The credential is valid but not permitted for this model or action (403)."""


class ModelRateLimitError(ModelError):
    """The provider throttled the request (HTTP 429 or equivalent)."""


class ModelTimeoutError(ModelError):
    """The single provider attempt exceeded the configured timeout."""


class ModelConnectionError(ModelError):
    """The provider endpoint could not be reached (DNS, TLS, socket)."""


class ModelInvalidRequestError(ModelError):
    """The provider rejected the request payload as malformed (HTTP 400)."""


class ModelProviderError(ModelError):
    """The provider returned an unclassified server-side failure (HTTP 5xx)."""


class ModelResponseNormalizationError(ModelError):
    """A syntactically successful provider response could not be normalized.

    Examples: missing required usage, malformed tool-call arguments, a tool call
    with neither a provider ID nor enough context to generate a deterministic one.
    """

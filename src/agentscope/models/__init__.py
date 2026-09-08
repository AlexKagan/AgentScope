"""AgentScope model boundary (design 7, Phase 1A.2).

The public surface other packages may import is deliberately small: the async
:class:`~agentscope.models.protocol.ModelAdapter` protocol, the normalized
request/response/usage/cost types, the safe identity, the registry, and the
error taxonomy. Provider-specific implementations (``openai_compatible``) and
LangChain types are *not* re-exported here and must not leak past the adapter.
"""

from __future__ import annotations

from agentscope.models.configuration import (
    BUILTIN_PROVIDER_PROFILES,
    Capability,
    ModelDefinition,
    ModelParameters,
    ReasoningConfig,
    ReasoningMode,
)
from agentscope.models.cost import CostSource, LLMCost, PriceCard, calculate_cost
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
from agentscope.models.identity import ProviderProfile, SafeModelIdentity, fingerprint
from agentscope.models.protocol import ModelAdapter
from agentscope.models.registry import ModelRegistry, ResolvedModel
from agentscope.models.requests import Message, ModelRequest, Role, ToolDefinition
from agentscope.models.responses import FinishReason, ModelResponse, ToolCall, ToolCallOrigin
from agentscope.models.usage import LLMUsage, normalize_usage

__all__ = [
    "BUILTIN_PROVIDER_PROFILES",
    "Capability",
    "CostSource",
    "FinishReason",
    "LLMCost",
    "LLMUsage",
    "Message",
    "ModelAdapter",
    "ModelAuthenticationError",
    "ModelAuthorizationError",
    "ModelCapabilityError",
    "ModelConfigurationError",
    "ModelConnectionError",
    "ModelDefinition",
    "ModelError",
    "ModelInvalidRequestError",
    "ModelParameters",
    "ModelProviderError",
    "ModelRateLimitError",
    "ModelRegistry",
    "ModelRequest",
    "ModelResponse",
    "ModelResponseNormalizationError",
    "ModelTimeoutError",
    "PriceCard",
    "ProviderProfile",
    "ReasoningConfig",
    "ReasoningMode",
    "ResolvedModel",
    "Role",
    "SafeModelIdentity",
    "ToolCall",
    "ToolCallOrigin",
    "ToolDefinition",
    "calculate_cost",
    "fingerprint",
    "normalize_usage",
]

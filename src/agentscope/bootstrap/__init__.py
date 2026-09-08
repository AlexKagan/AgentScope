"""AgentScope bootstrap - composition root.

The only package permitted to import ``agentscope.config.secret``.
"""

from agentscope.bootstrap.clients import ModelAdapterFactory, default_model_adapter_factory
from agentscope.bootstrap.composition import Platform, build_platform

__all__ = [
    "ModelAdapterFactory",
    "Platform",
    "build_platform",
    "default_model_adapter_factory",
]

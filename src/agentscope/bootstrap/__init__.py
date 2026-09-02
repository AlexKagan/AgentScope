"""AgentScope bootstrap - composition root.

The only package permitted to import ``agentscope.config.secret``.
"""

from agentscope.bootstrap.clients import ModelClientFactory, default_model_client_factory
from agentscope.bootstrap.composition import Platform, build_platform

__all__ = [
    "ModelClientFactory",
    "Platform",
    "build_platform",
    "default_model_client_factory",
]

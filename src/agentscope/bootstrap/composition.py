"""The trusted composition root (design 8.3, 12).

This module is the *only* place in ``agentscope`` that consumes
:class:`SecretConfig`. It turns credentials into constructed clients and
telemetry exporters, then injects those into a :class:`Platform`. Every other
component receives the narrowest capability it needs - never ``SecretConfig``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from agentscope.architectures.registry import ArchitectureRegistry
from agentscope.bootstrap.clients import ModelClientFactory, default_model_client_factory
from agentscope.config.public import PublicConfig
from agentscope.config.secret import SecretConfig
from agentscope.telemetry.noop import NoOpSink
from agentscope.telemetry.sink import TelemetrySink

__all__ = ["Platform", "build_platform"]

TelemetryFactory = Callable[[PublicConfig, SecretConfig], TelemetrySink]


@dataclass(frozen=True, slots=True)
class Platform:
    """The wired platform: public config plus injected capabilities."""

    config: PublicConfig
    registry: ArchitectureRegistry
    telemetry: TelemetrySink
    model_client: object | None = field(default=None, repr=False)


def build_platform(
    public: PublicConfig,
    secret: SecretConfig,
    *,
    registry: ArchitectureRegistry | None = None,
    model_client_factory: ModelClientFactory | None = None,
    telemetry_factory: TelemetryFactory | None = None,
) -> Platform:
    """Compose a :class:`Platform` from validated public and secret config."""
    registry = registry or ArchitectureRegistry()

    telemetry: TelemetrySink
    if public.telemetry_enabled:
        if telemetry_factory is None:
            from agentscope.telemetry.phoenix import configure_phoenix

            telemetry_factory = configure_phoenix
        telemetry = telemetry_factory(public, secret)
    else:
        telemetry = NoOpSink()

    model_client: object | None = None
    model_id = public.model_identifier
    if model_id is not None:
        factory = model_client_factory or default_model_client_factory
        model_client = factory(model_id, secret.require("openai_api_key"))

    return Platform(
        config=public,
        registry=registry,
        telemetry=telemetry,
        model_client=model_client,
    )

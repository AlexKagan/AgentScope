"""Component test: snapshots never carry seeded secrets (design 13.2, 17)."""

from __future__ import annotations

import json

from agentscope.bootstrap.composition import build_platform
from agentscope.config.public import PublicConfig
from agentscope.config.secret import SecretConfig
from agentscope.models.configuration import ModelDefinition
from tests._fakes import FakeModelAdapterFactory

_META = ModelDefinition(
    key="primary-reasoner",
    provider="meta",
    model_name="muse-spark-1.3",
    credential_ref="meta_model_api_key",
)


def test_public_config_snapshot_has_no_secret(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    cfg = PublicConfig(primary_model_key="primary-reasoner", models={"primary-reasoner": _META})
    blob = json.dumps(cfg.safe_dump()) + repr(cfg) + cfg.model_dump_json()
    for secret in all_fake_secrets:
        assert secret not in blob


def test_platform_repr_has_no_secret_even_after_adapter_build(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    platform = build_platform(
        PublicConfig(primary_model_key="primary-reasoner", models={"primary-reasoner": _META}),
        SecretConfig(),  # type: ignore[call-arg]
        model_adapter_factory=FakeModelAdapterFactory(),
    )
    blob = repr(platform) + repr(platform.config)
    for secret in all_fake_secrets:
        assert secret not in blob

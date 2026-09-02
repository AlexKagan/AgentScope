"""Component test: snapshots never carry seeded secrets (design 13.2, 17)."""

from __future__ import annotations

import json

from agentscope.bootstrap.composition import build_platform
from agentscope.config.public import PublicConfig
from agentscope.config.secret import SecretConfig
from tests._fakes import FakeModelClientFactory


def test_public_config_snapshot_has_no_secret(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    cfg = PublicConfig()  # type: ignore[call-arg]
    blob = json.dumps(cfg.safe_dump()) + repr(cfg) + cfg.model_dump_json()
    for secret in all_fake_secrets:
        assert secret not in blob


def test_platform_repr_has_no_secret_even_after_client_build(
    seeded_secret_env: dict[str, str], all_fake_secrets: tuple[str, ...]
) -> None:
    platform = build_platform(
        PublicConfig(primary_model="openai:gpt-x"),  # type: ignore[call-arg]
        SecretConfig(),  # type: ignore[call-arg]
        model_client_factory=FakeModelClientFactory(),
    )
    blob = repr(platform) + repr(platform.config)
    for secret in all_fake_secrets:
        assert secret not in blob

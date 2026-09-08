"""Opt-in Meta Model API live smoke (design 11.4, plan §15).

Excluded from the default run. Enable with::

    uv run pytest -m meta_model_api

Needs ``AGENTSCOPE_META_MODEL_API_KEY`` (from your shell env or the local,
git-ignored ``.env``). Verifies the documented Meta cookbook contract —
OpenAI-compatible Chat Completions at ``https://api.meta.ai/v1`` with
``muse-spark-1.3`` and native function/tool calling — through the same
``OpenAICompatibleChatAdapter`` (LangChain ``ChatOpenAI``). The smoke model can be
overridden with AGENTSCOPE_META_SMOKE_MODEL because account availability changes.
Record any incompatibility in docs/findings/ before adding a specialized adapter.
"""

from __future__ import annotations

import os

import pytest

from agentscope.config.secret import SecretConfig
from agentscope.models.configuration import ModelDefinition
from tests.external._model_smoke import run_model_smoke

pytestmark = [pytest.mark.external, pytest.mark.meta_model_api]

_DEFAULT_SMOKE_MODEL = "muse-spark-1.3"


def test_meta_model_api_plain_and_structured_contract() -> None:
    secret = SecretConfig().meta_model_api_key  # reads .env and AGENTSCOPE_* env
    if secret is None:
        pytest.skip("AGENTSCOPE_META_MODEL_API_KEY not set (shell env or .env)")

    definition = ModelDefinition(
        key="meta-smoke",
        provider="meta",
        protocol="openai-chat-completions",
        model_name=os.environ.get("AGENTSCOPE_META_SMOKE_MODEL", _DEFAULT_SMOKE_MODEL),
        credential_ref="meta_model_api_key",
        timeout_s=60.0,
    )
    assert definition.resolved_base_url == "https://api.meta.ai/v1"
    run_model_smoke(definition, secret.get_secret_value())

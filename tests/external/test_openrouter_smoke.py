"""Opt-in OpenRouter live smoke (design 11.4).

Excluded from the default run. Enable with::

    uv run pytest -m openrouter

Needs ``AGENTSCOPE_OPENROUTER_API_KEY`` (from your shell env or the local,
git-ignored ``.env``). Uses the generic ``OpenAICompatibleChatAdapter`` against
OpenRouter's pinned HTTPS endpoint. The smoke model is explicit public
configuration and inexpensive; override it with
``AGENTSCOPE_OPENROUTER_SMOKE_MODEL`` if account availability changes.
"""

from __future__ import annotations

import os

import pytest

from agentscope.config.secret import SecretConfig
from agentscope.models.configuration import ModelDefinition
from tests.external._model_smoke import run_model_smoke

pytestmark = [pytest.mark.external, pytest.mark.openrouter]

_DEFAULT_SMOKE_MODEL = "openai/gpt-4o-mini"


def test_openrouter_plain_and_structured_contract() -> None:
    secret = SecretConfig().openrouter_api_key  # reads .env and AGENTSCOPE_* env
    if secret is None:
        pytest.skip("AGENTSCOPE_OPENROUTER_API_KEY not set (shell env or .env)")

    definition = ModelDefinition(
        key="openrouter-smoke",
        provider="openrouter",
        model_name=os.environ.get("AGENTSCOPE_OPENROUTER_SMOKE_MODEL", _DEFAULT_SMOKE_MODEL),
        credential_ref="openrouter_api_key",
        timeout_s=60.0,
    )
    # Confirms the generic adapter is what serves OpenRouter.
    assert definition.resolved_base_url == "https://openrouter.ai/api/v1"
    run_model_smoke(definition, secret.get_secret_value())

"""Model definitions, provider profiles, and endpoint policy (design 7.1, 8.4)."""

from __future__ import annotations

import pytest

from agentscope.config.secret import SecretConfig
from agentscope.models.configuration import (
    ALLOWED_CREDENTIAL_REFS,
    BUILTIN_PROVIDER_PROFILES,
    Capability,
    ModelDefinition,
    validate_endpoint,
)
from agentscope.models.errors import ModelConfigurationError


def _defn(**over: object) -> ModelDefinition:
    base: dict[str, object] = {
        "key": "primary-reasoner",
        "provider": "meta",
        "model_name": "muse-spark-1.3",
        "credential_ref": "meta_model_api_key",
    }
    base.update(over)
    return ModelDefinition(**base)  # type: ignore[arg-type]


def test_valid_definition_uses_pinned_endpoint_and_declares_capabilities() -> None:
    d = _defn()
    assert d.resolved_base_url == "https://api.meta.ai/v1"
    assert Capability.TEXT in d.capabilities
    assert d.supports(Capability.TOOL_CALLING)


def test_allowed_credential_refs_match_secretconfig_fields() -> None:
    secret_fields = set(SecretConfig.model_fields)
    assert secret_fields >= ALLOWED_CREDENTIAL_REFS


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(provider="acme")


def test_unknown_protocol_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(protocol="openai-responses")


def test_unknown_credential_ref_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(credential_ref="acme_key")


def test_non_allowlisted_request_option_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(request_options={"logprobs": True})


def test_definition_without_text_capability_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(capabilities=(Capability.TOOL_CALLING,))


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://api.meta.ai/v1",
        "https://user:pass@api.meta.ai/v1",
        "https://api.meta.ai/v1?token=abc",
        "https://api.meta.ai/v1#frag",
        "https://api.meta.ai/../v1",
        "ftp://api.meta.ai/v1",
    ],
)
def test_unsafe_endpoint_is_rejected(bad_url: str) -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(base_url=bad_url)


def test_local_http_allowed_only_behind_dev_flag() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(base_url="http://localhost:8000/v1")
    ok = _defn(base_url="http://localhost:8000/v1", allow_insecure_http=True)
    assert ok.resolved_base_url == "http://localhost:8000/v1"


def test_validate_endpoint_returns_input_when_safe() -> None:
    assert validate_endpoint("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"


def test_profiles_pin_https_urls() -> None:
    for profile in BUILTIN_PROVIDER_PROFILES.values():
        assert profile.base_url.startswith("https://")


def test_definition_is_frozen() -> None:
    d = _defn()
    with pytest.raises(Exception):  # noqa: B017 - pydantic raises ValidationError
        d.model_name = "other"  # type: ignore[misc]

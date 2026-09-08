"""Model definitions, provider profiles, and endpoint policy (design 7.1, 8.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
    assert d.resolved_endpoint == "https://api.meta.ai/v1"
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


def test_credential_ref_must_match_provider_profile() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(credential_ref="openrouter_api_key")


def test_non_allowlisted_provider_option_is_rejected() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(provider_options={"secret_option": True})


def test_unknown_portable_parameter_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _defn(parameters={"secret_option": "x"})


@pytest.mark.parametrize("effort", ["", "extreme", 7])
def test_invalid_reasoning_effort_is_rejected(effort: object) -> None:
    with pytest.raises(ValidationError):
        _defn(reasoning={"mode": "enabled", "effort": effort})


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"temperature": float("nan")}, "finite"),
        ({"top_p": True}, "finite"),
        ({"max_output_tokens": 0}, "greater than 0"),
        ({"max_output_tokens": 1.5}, "integer"),
        ({"stop": 4}, "string"),
    ],
)
def test_invalid_request_option_values_are_rejected(
    options: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _defn(parameters=options)


@pytest.mark.parametrize("name", [" muse-spark-1.3", "muse spark", "sk-secretvalue123"])
def test_unsafe_model_name_is_rejected(name: str) -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(model_name=name)


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
        _defn(endpoint=bad_url)


def test_local_http_allowed_only_behind_dev_flag() -> None:
    with pytest.raises(ModelConfigurationError):
        _defn(endpoint="http://localhost:8000/v1")
    ok = _defn(endpoint="http://localhost:8000/v1", allow_insecure_http=True)
    assert ok.resolved_endpoint == "http://localhost:8000/v1"


def test_validate_endpoint_returns_input_when_safe() -> None:
    assert validate_endpoint("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"


def test_profiles_pin_https_urls() -> None:
    for profile in BUILTIN_PROVIDER_PROFILES.values():
        assert profile.base_url.startswith("https://")


def test_definition_is_frozen() -> None:
    d = _defn()
    with pytest.raises(Exception):  # noqa: B017 - pydantic raises ValidationError
        d.model_name = "other"  # type: ignore[misc]


def test_definition_nested_options_are_immutable() -> None:
    options = {"logprobs": True}
    d = _defn(provider_options=options)
    options["logprobs"] = False
    assert d.provider_options["logprobs"] is True
    with pytest.raises(TypeError):
        d.provider_options["logprobs"] = True  # type: ignore[index]


@pytest.mark.parametrize("mode", ["provider_default", "disabled"])
def test_non_enabled_reasoning_rejects_details(mode: str) -> None:
    with pytest.raises(ValidationError, match="require mode='enabled'"):
        _defn(reasoning={"mode": mode, "effort": "low"})


def test_enabled_reasoning_requires_exactly_one_control() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        _defn(capabilities=["text", "reasoning"], reasoning={"mode": "enabled"})
    with pytest.raises(ValidationError, match="exactly one"):
        _defn(
            capabilities=["text", "reasoning"],
            reasoning={"mode": "enabled", "effort": "low", "max_tokens": 100},
        )


def test_enabled_reasoning_requires_declared_capability() -> None:
    with pytest.raises(ModelConfigurationError, match=r"reasoning.*capability"):
        _defn(reasoning={"mode": "enabled", "effort": "low"})


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_meta_rejects_unverified_reasoning_translation(mode: str) -> None:
    reasoning: dict[str, object] = {"mode": mode}
    if mode == "enabled":
        reasoning["effort"] = "low"
    with pytest.raises(ModelConfigurationError, match=r"no verified.*reasoning translation"):
        _defn(capabilities=["text", "reasoning"], reasoning=reasoning)


@pytest.mark.parametrize(
    "parameters",
    [{"max_output_tokens": True}, {"seed": True}],
)
def test_integer_parameters_reject_booleans(parameters: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="must not be a boolean"):
        _defn(parameters=parameters)


def test_reasoning_token_budget_rejects_boolean() -> None:
    with pytest.raises(ValidationError, match="must not be a boolean"):
        _defn(
            provider="openrouter",
            credential_ref="openrouter_api_key",
            capabilities=["text", "reasoning"],
            reasoning={"mode": "enabled", "max_tokens": True},
        )

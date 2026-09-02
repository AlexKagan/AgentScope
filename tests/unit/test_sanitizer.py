"""Unit tests for telemetry sanitization (design 9, 13.1)."""

from __future__ import annotations

from pydantic import SecretStr

from agentscope.telemetry.events import TelemetryEvent
from agentscope.telemetry.sanitizer import MAX_VALUE_LEN, REDACTED, Sanitizer


def test_top_level_sensitive_key_redacted() -> None:
    out = Sanitizer().sanitize_mapping({"api_key": "sk-secretvalue"})
    assert out == {"api_key": REDACTED}


def test_nested_mappings_and_sequences_redacted() -> None:
    payload = {
        "outer": {"authorization": "Bearer abc"},
        "list": [{"password": "hunter2"}, {"ok": "keep"}],
    }
    out = Sanitizer().sanitize_mapping(payload)
    assert out["outer"]["authorization"] == REDACTED
    assert out["list"][0]["password"] == REDACTED
    assert out["list"][1]["ok"] == "keep"


def test_sensitive_key_casing_and_variants() -> None:
    out = Sanitizer().sanitize_mapping(
        {
            "Authorization": "x",
            "CLIENT_SECRET": "x",
            "private-key": "x",
            "Cookie": "x",
            "access_token": "x",
        }
    )
    assert set(out.values()) == {REDACTED}


def test_value_shaped_secret_scrubbed_under_benign_key() -> None:
    out = Sanitizer().sanitize_mapping({"note": "use sk-ABCDEFGHIJKLMNOerty please"})
    assert "sk-ABCDEFGHIJKLMNOerty" not in out["note"]
    assert REDACTED in out["note"]


def test_long_values_truncated() -> None:
    # "x" is not hex / not secret-shaped, so only truncation applies.
    out = Sanitizer().sanitize_mapping({"blob": "x" * (MAX_VALUE_LEN + 500)})
    assert len(out["blob"]) <= MAX_VALUE_LEN + len("...(truncated)")
    assert out["blob"].endswith("...(truncated)")


def test_exception_message_and_type_sanitized() -> None:
    out = Sanitizer().sanitize_exception(ValueError("token=sk-DEADBEEFDEADBEEF12"))
    assert out["type"] == "ValueError"
    assert "sk-DEADBEEFDEADBEEF12" not in out["message"]


def test_secretstr_always_redacted() -> None:
    out = Sanitizer().sanitize_mapping(
        {"benign": SecretStr("hunter2"), "deep": {"x": SecretStr("y")}}
    )
    assert out["benign"] == REDACTED
    assert out["deep"]["x"] == REDACTED


def test_fail_closed_for_unexpected_value_type() -> None:
    class Weird:
        def __repr__(self) -> str:  # pragma: no cover - must never be called
            return "sk-LEAKED-THROUGH-REPR"

    out = Sanitizer().sanitize_mapping({"api_key": Weird()})
    assert out["api_key"] == REDACTED


def test_sanitize_event_preserves_name() -> None:
    ev = Sanitizer().sanitize_event(TelemetryEvent("model.call", {"api_key": "x", "n": 1}))
    assert ev.name == "model.call"
    assert ev.attributes == {"api_key": REDACTED, "n": 1}


def test_benign_env_shaped_mapping_passes_through() -> None:
    payload = {"LANG": "en_US.UTF-8", "PATH": "/usr/bin", "count": 3}
    assert Sanitizer().sanitize_mapping(payload) == payload

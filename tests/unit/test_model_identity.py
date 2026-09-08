"""Safe model identity and reproducibility fingerprint (design 7, D3)."""

from __future__ import annotations

from decimal import Decimal

from agentscope.models.configuration import ModelDefinition
from agentscope.models.cost import PriceCard


def _defn(**over: object) -> ModelDefinition:
    base: dict[str, object] = {
        "key": "primary-reasoner",
        "provider": "meta",
        "model_name": "muse-spark-1.3",
        "credential_ref": "meta_model_api_key",
    }
    base.update(over)
    return ModelDefinition(**base)  # type: ignore[arg-type]


def test_fingerprint_is_deterministic() -> None:
    assert _defn().fingerprint() == _defn().fingerprint()


def test_identity_carries_no_secret_value() -> None:
    ident = _defn().identity()
    blob = repr(ident)
    assert "meta_model_api_key" in blob  # symbolic ref is fine
    assert "sk-" not in blob


def test_fingerprint_changes_for_every_behavior_affecting_option() -> None:
    base = _defn().fingerprint()
    assert _defn(model_name="muse-spark-2.0").fingerprint() != base
    assert _defn(provider="openrouter", credential_ref="openrouter_api_key").fingerprint() != base
    assert _defn(request_options={"temperature": 0.1}).fingerprint() != base
    assert _defn(reasoning_options={"effort": "high"}).fingerprint() != base
    assert _defn(adapter_version="2.0.0").fingerprint() != base
    assert _defn(tool_schema_version="9.9.9").fingerprint() != base
    priced = _defn(
        pricing=PriceCard(
            pricing_id="meta-muse",
            version="2026-01",
            input_usd_per_mtok=Decimal("1"),
            output_usd_per_mtok=Decimal("2"),
        )
    )
    assert priced.fingerprint() != base


def test_fingerprint_stable_across_credential_rotation() -> None:
    # credential_ref is symbolic; the identity never sees the secret, so nothing
    # about the fingerprint depends on the credential value.
    assert _defn().fingerprint() == _defn().fingerprint()


def test_fingerprint_is_hex_sha256() -> None:
    fp = _defn().fingerprint()
    assert len(fp) == 64
    int(fp, 16)

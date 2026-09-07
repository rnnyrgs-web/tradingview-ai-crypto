import json

from promotion_manifest import approval_signature, find_verified_promotion, verify_promotion
from research_artifact import seal_research_payload, verify_research_envelope
from strategy_identity import build_strategy_identity
from tools.sign_promotion import sign_document


def _promotion(identity):
    return {
        "schema_version": 1,
        "status": "APPROVED",
        "identity": identity,
        "evidence_sha256": ["a" * 64, "b" * 64, "c" * 64],
        "stages": {
            "repeated_backtests": True,
            "validation": True,
            "untouched_oos": True,
            "robustness_stability": True,
            "strategy_registry": True,
            "production_risk": True,
        },
        "approvals": {},
    }


def _sign(promotion, monkeypatch):
    registry_key = "r" * 32
    risk_key = "p" * 32
    monkeypatch.setenv("STRATEGY_REGISTRY_SIGNING_KEY", registry_key)
    monkeypatch.setenv("PRODUCTION_RISK_SIGNING_KEY", risk_key)
    promotion["approvals"] = {
        "strategy_registry": {"signature": approval_signature(promotion, "strategy_registry", registry_key)},
        "production_risk": {"signature": approval_signature(promotion, "production_risk", risk_key)},
    }


def test_research_envelope_detects_tampering():
    envelope = seal_research_payload({"result": "WAIT", "trades": 20})
    assert verify_research_envelope(envelope) is True
    envelope["payload"]["trades"] = 21
    assert verify_research_envelope(envelope) is False


def test_promotion_requires_three_research_artifacts_and_all_stages(monkeypatch):
    identity = build_strategy_identity("ETH-USDT", "24h", "trend")
    promotion = _promotion(identity)
    promotion["evidence_sha256"] = ["a" * 64, "b" * 64]
    _sign(promotion, monkeypatch)
    assert verify_promotion(promotion, identity)[0] is False

    promotion = _promotion(identity)
    promotion["stages"]["robustness_stability"] = False
    _sign(promotion, monkeypatch)
    assert verify_promotion(promotion, identity)[0] is False


def test_promotion_requires_both_valid_independent_signatures(monkeypatch):
    identity = build_strategy_identity("ETH-USDT", "24h", "trend")
    promotion = _promotion(identity)
    _sign(promotion, monkeypatch)
    assert verify_promotion(promotion, identity)[0] is True
    promotion["approvals"]["production_risk"]["signature"] = "0" * 64
    assert verify_promotion(promotion, identity)[0] is False


def test_exact_verified_manifest_can_be_found(tmp_path, monkeypatch):
    identity = build_strategy_identity("ETH-USDT", "24h", "trend")
    promotion = _promotion(identity)
    _sign(promotion, monkeypatch)
    path = tmp_path / "promotions.json"
    path.write_text(json.dumps({"schema_version": 1, "promotions": [promotion]}), encoding="utf-8")
    assert find_verified_promotion(identity, path)[0] is True
    other = build_strategy_identity("ETH-USDT", "7d", "trend")
    assert find_verified_promotion(other, path)[0] is False


def test_role_signing_is_independent_and_exact(monkeypatch):
    identity = build_strategy_identity("ETH-USDT", "24h", "trend")
    promotion = _promotion(identity)
    document = {"schema_version": 1, "promotions": [promotion]}
    sign_document(document, identity["fingerprint"], "strategy_registry", "r" * 32)
    assert set(promotion["approvals"]) == {"strategy_registry"}
    monkeypatch.setenv("STRATEGY_REGISTRY_SIGNING_KEY", "r" * 32)
    monkeypatch.setenv("PRODUCTION_RISK_SIGNING_KEY", "p" * 32)
    assert verify_promotion(promotion, identity)[0] is False
    sign_document(document, identity["fingerprint"], "production_risk", "p" * 32)
    assert verify_promotion(promotion, identity)[0] is True


def test_malformed_entries_and_short_keys_fail_closed(tmp_path, monkeypatch):
    identity = build_strategy_identity("ETH-USDT", "24h", "trend")
    promotion = _promotion(identity)
    monkeypatch.setenv("STRATEGY_REGISTRY_SIGNING_KEY", "short")
    monkeypatch.setenv("PRODUCTION_RISK_SIGNING_KEY", "short")
    assert verify_promotion(promotion, identity)[0] is False
    path = tmp_path / "promotions.json"
    path.write_text(json.dumps({"schema_version": 1, "promotions": [None, 42]}), encoding="utf-8")
    assert find_verified_promotion(identity, path)[0] is False

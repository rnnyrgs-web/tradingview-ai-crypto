import production_validation as pv


def test_live_validation_rejects_missing_identity():
    decision = pv.validate_live_strategy("BTC-USDT", "24h", "")
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"
    assert decision.identity["identity_complete"] is False
    assert decision.identity["fingerprint"] == ""


def test_live_validation_rejects_unsupported_family_without_fingerprint():
    decision = pv.validate_live_strategy("BTC-USDT", "24h", "unknown_strategy")
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"
    assert decision.reason == "Unsupported or incomplete exact strategy identity."
    assert decision.identity["identity_complete"] is False
    assert decision.identity["fingerprint"] == ""


def test_live_validation_rejects_unpromoted_strategy():
    decision = pv.validate_live_strategy("ETH-USDT", "24h", "trend")
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"


def test_signed_promotion_still_fails_without_forward_proof(monkeypatch):
    monkeypatch.setattr(pv, "find_verified_promotion", lambda identity: (True, "verified"))
    decision = pv.validate_live_strategy("ETH-USDT", "24h", "trend", [])
    assert decision.approved is False
    assert decision.status == "FORWARD_PROOF_REQUIRED"
    assert decision.forward_proof["passed"] is False


def test_live_validation_requires_exact_promoted_key_and_forward_proof(monkeypatch):
    approved_fingerprint = pv.build_strategy_identity("ETH-USDT", "24h", "trend")["fingerprint"]
    monkeypatch.setattr(pv, "find_verified_promotion", lambda identity: (
        identity["fingerprint"] == approved_fingerprint,
        "verified" if identity["fingerprint"] == approved_fingerprint else "not verified",
    ))
    monkeypatch.setattr(pv, "assess_forward_proof", lambda identity, horizon, rows: {
        "passed": identity["fingerprint"] == approved_fingerprint and horizon == "24h",
        "reason": "forward_proof_passed",
    })
    assert pv.validate_live_strategy("eth-usdt", "24h", "TREND", [{}]).approved is True
    assert pv.validate_live_strategy("ETH-USDT", "7d", "trend", [{}]).approved is False
    assert pv.validate_live_strategy("ETH-USDT", "24h", "breakout", [{}]).approved is False


def test_identity_is_exact_and_exposed_in_decision():
    decision = pv.validate_live_strategy("eth-usdt", "24h", "TREND")
    identity = decision.identity
    assert identity["symbol"] == "ETH-USDT"
    assert identity["production_horizon"] == "24h"
    assert identity["timeframes"] == ["1H", "4H"]
    assert identity["identity_complete"] is True
    assert len(identity["research_code_sha256"]) == 64
    assert len(identity["fingerprint"]) == 64


def test_unknown_horizon_fails_closed_without_fingerprint():
    decision = pv.validate_live_strategy("ETH-USDT", "2d", "trend")
    assert decision.approved is False
    assert decision.identity["timeframes"] == []
    assert decision.identity["identity_complete"] is False
    assert decision.identity["fingerprint"] == ""

import production_validation as pv


def test_live_validation_rejects_missing_identity():
    decision = pv.validate_live_strategy("BTC-USDT", "24h", "")
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"


def test_live_validation_rejects_unpromoted_strategy():
    decision = pv.validate_live_strategy("ETH-USDT", "24h", "trend")
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"


def test_live_validation_requires_exact_promoted_key(monkeypatch):
    approved_fingerprint = pv.build_strategy_identity("ETH-USDT", "24h", "trend")["fingerprint"]
    monkeypatch.setattr(pv, "find_verified_promotion", lambda identity: (
        identity["fingerprint"] == approved_fingerprint,
        "verified" if identity["fingerprint"] == approved_fingerprint else "not verified",
    ))
    assert pv.validate_live_strategy("eth-usdt", "24h", "TREND").approved is True
    assert pv.validate_live_strategy("ETH-USDT", "7d", "trend").approved is False
    assert pv.validate_live_strategy("ETH-USDT", "24h", "breakout").approved is False


def test_identity_is_exact_and_exposed_in_decision():
    decision = pv.validate_live_strategy("eth-usdt", "24h", "TREND")
    identity = decision.identity
    assert identity["symbol"] == "ETH-USDT"
    assert identity["production_horizon"] == "24h"
    assert identity["timeframes"] == ["1H", "4H"]
    assert len(identity["research_code_sha256"]) == 64
    assert len(identity["fingerprint"]) == 64


def test_unknown_horizon_fails_closed():
    decision = pv.validate_live_strategy("ETH-USDT", "2d", "trend")
    assert decision.approved is False
    assert decision.identity["timeframes"] == []

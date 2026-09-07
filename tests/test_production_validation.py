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
    monkeypatch.setattr(
        pv,
        "LIVE_VALIDATED_STRATEGIES",
        frozenset({("ETH-USDT", "24h", "trend")}),
    )
    assert pv.validate_live_strategy("eth-usdt", "24h", "TREND").approved is True
    assert pv.validate_live_strategy("ETH-USDT", "7d", "trend").approved is False
    assert pv.validate_live_strategy("ETH-USDT", "24h", "breakout").approved is False

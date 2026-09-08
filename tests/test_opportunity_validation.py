import opportunity_engine as oe


def _risk_plan(features, direction, horizon):
    if direction == "LONG":
        return {"entry": 100.0, "stop": 90.0, "t1": 119.0, "t2": 130.0, "rr": 1.9}
    return {"entry": 100.0, "stop": 110.0, "t1": 81.0, "t2": 70.0, "rr": 1.9}


def test_ai_trade_is_downgraded_without_full_research_validation(monkeypatch):
    persisted = []
    monkeypatch.setattr(oe, "replace_opportunities", lambda scan_id, horizon, rows: persisted.extend(rows))
    monkeypatch.setattr(oe, "insert_prediction_ledger", lambda rows: None)
    monkeypatch.setattr(oe, "fetch_resolved_predictions", lambda: [])
    candidates = [{
        "symbol": "ETH-USDT",
        "activity_score": 10.0,
        "spread_bps": 2.0,
        "market_consensus": {"reliable": True, "reason": "ok"},
        "horizons": {"24h": {"score": 2.0, "features": {"1H": {"last": 100.0}}}},
    }]
    ai_signals = [{
        "symbol": "ETH-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "strategy_family": "trend",
        "action": "TRADE",
        "evidence_score": 90,
        "reasoning": "Looks strong",
    }]

    result = oe.build_opportunities("scan", candidates, ai_signals, "BULL_TREND", _risk_plan)

    assert result["24h"][0]["action"] == "WAIT"
    assert "RESEARCH_ONLY" in result["24h"][0]["reasoning"]


def test_exact_promoted_strategy_can_preserve_trade(monkeypatch):
    persisted = []
    monkeypatch.setattr(oe, "replace_opportunities", lambda scan_id, horizon, rows: persisted.extend(rows))
    monkeypatch.setattr(oe, "insert_prediction_ledger", lambda rows: None)
    monkeypatch.setattr(oe, "fetch_resolved_predictions", lambda: [
        {"horizon":"24h","score":90,"market_regime":"BULL_TREND","correct":True}
        for _ in range(30)
    ])
    monkeypatch.setattr(
        oe,
        "validate_live_strategy",
        lambda *args: type("D", (), {
            "approved": True,
            "status": "LIVE_VALIDATED",
            "reason": "approved",
            "identity": {"fingerprint": "a" * 64},
        })(),
    )
    candidates = [{
        "symbol": "ETH-USDT",
        "activity_score": 10.0,
        "spread_bps": 2.0,
        "market_consensus": {"reliable": True, "reason": "ok"},
        "horizons": {"24h": {"score": 2.0, "features": {"1H": {"last": 100.0}}}},
    }]
    ai_signals = [{
        "symbol": "ETH-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "strategy_family": "trend",
        "action": "TRADE",
        "evidence_score": 90,
        "reasoning": "Looks strong",
    }]

    result = oe.build_opportunities("scan", candidates, ai_signals, "BULL_TREND", _risk_plan)
    assert result["24h"][0]["action"] == "TRADE"


def test_unreliable_market_consensus_blocks_otherwise_promoted_trade(monkeypatch):
    monkeypatch.setattr(oe, "replace_opportunities", lambda *args: None)
    monkeypatch.setattr(oe, "insert_prediction_ledger", lambda rows: None)
    monkeypatch.setattr(oe, "fetch_resolved_predictions", lambda: [
        {"horizon":"24h","score":90,"market_regime":"BULL_TREND","correct":True}
        for _ in range(30)
    ])
    monkeypatch.setattr(
        oe, "validate_live_strategy",
        lambda *args: type("D", (), {
            "approved": True, "status": "LIVE_VALIDATED", "reason": "approved",
            "identity": {"fingerprint": "a" * 64},
        })(),
    )
    candidates = [{
        "symbol": "ETH-USDT", "activity_score": 10.0, "spread_bps": 2.0,
        "market_consensus": {"reliable": False, "reason": "exchange_price_disagreement"},
        "horizons": {"24h": {"score": 2.0, "features": {"1H": {"last": 100.0}}}},
    }]
    signals = [{
        "symbol": "ETH-USDT", "horizon": "24h", "direction": "LONG",
        "strategy_family": "trend", "action": "TRADE", "evidence_score": 90,
    }]
    result = oe.build_opportunities("scan", candidates, signals, "BULL_TREND", _risk_plan)
    assert result["24h"][0]["action"] == "WAIT"
    assert "MARKET_CONSENSUS_UNRELIABLE" in result["24h"][0]["reasoning"]

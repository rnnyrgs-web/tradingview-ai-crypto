import opportunity_engine as oe


def _risk_plan(features, direction, horizon):
    if direction == "LONG":
        return {"entry": 100.0, "stop": 90.0, "t1": 119.0, "t2": 130.0, "rr": 1.9}
    return {"entry": 100.0, "stop": 110.0, "t1": 81.0, "t2": 70.0, "rr": 1.9}


def test_ai_trade_is_downgraded_without_full_research_validation(monkeypatch):
    persisted = []
    monkeypatch.setattr(oe, "replace_opportunities", lambda scan_id, horizon, rows: persisted.extend(rows))
    candidates = [{
        "symbol": "ETH-USDT",
        "activity_score": 10.0,
        "spread_bps": 2.0,
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
    monkeypatch.setattr(
        oe,
        "validate_live_strategy",
        lambda symbol, horizon, family: type("D", (), {"approved": True, "status": "LIVE_VALIDATED", "reason": "approved"})(),
    )
    candidates = [{
        "symbol": "ETH-USDT",
        "activity_score": 10.0,
        "spread_bps": 2.0,
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

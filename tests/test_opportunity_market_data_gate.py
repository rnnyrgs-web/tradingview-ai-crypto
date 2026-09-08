from types import SimpleNamespace

import opportunity_engine


def _candidate(consensus):
    features = {"atr": 1.0, "last": 100.0}
    return {
        "symbol": "TEST-USDT",
        "activity_score": 10.0,
        "spread_bps": 2.0,
        "market_consensus": consensus,
        "horizons": {
            "24h": {"score": 4.0, "features": features},
            "7d": {"score": 4.0, "features": features},
        },
    }


def _risk_plan(_features, _direction, _horizon):
    return {"entry": 100.0, "stop": 95.0, "t1": 108.0, "t2": 110.0, "rr": 2.0}


def _setup(monkeypatch):
    saved = []
    ledgers = []
    monkeypatch.setattr(opportunity_engine, "fetch_resolved_predictions", lambda: [])
    monkeypatch.setattr(
        opportunity_engine,
        "validate_live_strategy",
        lambda *_args: SimpleNamespace(approved=True, status="APPROVED", reason="ok", identity="id"),
    )
    monkeypatch.setattr(
        opportunity_engine,
        "calibration_assessment",
        lambda evidence, *_args: {"allows_live_action": True, "evidence": evidence},
    )
    monkeypatch.setattr(
        opportunity_engine,
        "assess_execution_risk",
        lambda *_args, **_kwargs: SimpleNamespace(blocked=False, reasons=()),
    )
    monkeypatch.setattr(opportunity_engine, "replace_opportunities", lambda scan, horizon, rows: saved.append((horizon, rows)))
    monkeypatch.setattr(opportunity_engine, "insert_prediction_ledger", lambda rows: ledgers.extend(rows))
    return saved, ledgers


def _ai():
    return [
        {"symbol": "TEST-USDT", "horizon": "24h", "direction": "LONG", "action": "TRADE", "strategy_family": "trend", "evidence_score": 80},
        {"symbol": "TEST-USDT", "horizon": "7d", "direction": "LONG", "action": "TRADE", "strategy_family": "trend", "evidence_score": 80},
    ]


def test_reliable_consensus_preserves_evidence_and_trade_eligibility(monkeypatch):
    _setup(monkeypatch)
    candidate = _candidate({"reliable": True, "reason": "ok", "confidence_multiplier": 1.0})
    result = opportunity_engine.build_opportunities("scan", [candidate], _ai(), "RANGE", _risk_plan)
    assert result["24h"][0]["action"] == "TRADE"
    assert result["24h"][0]["evidence_score"] == 80


def test_single_source_restricts_evidence_and_forces_wait(monkeypatch):
    _setup(monkeypatch)
    candidate = _candidate({
        "reliable": False,
        "reason": "insufficient_independent_sources",
        "source_count": 1,
        "confidence_multiplier": 0.4,
        "provenance": {"accepted_exchange_names": ["okx"]},
    })
    result = opportunity_engine.build_opportunities("scan", [candidate], _ai(), "RANGE", _risk_plan)
    row = result["24h"][0]
    assert row["action"] == "WAIT"
    assert row["evidence_score"] == 32
    assert "MARKET_DATA_RESTRICTED" in row["reasoning"]


def test_cross_exchange_contradiction_collapses_market_confidence(monkeypatch):
    _setup(monkeypatch)
    candidate = _candidate({
        "reliable": False,
        "reason": "exchange_price_disagreement",
        "source_count": 2,
        "confidence_multiplier": 0.0,
        "provenance": {"accepted_exchange_names": ["binance", "okx"]},
    })
    result = opportunity_engine.build_opportunities("scan", [candidate], _ai(), "RANGE", _risk_plan)
    row = result["24h"][0]
    assert row["action"] == "WAIT"
    assert row["evidence_score"] == 0.0

import importlib
import sys
from types import SimpleNamespace

import pytest

import config
import opportunity_engine as oe
from market_intelligence import cross_exchange_order_book


def _load_engine(monkeypatch):
    # The OpenAI client validates that a key exists at construction; no request is made.
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-only-key")
    sys.modules.pop("engine", None)
    return importlib.import_module("engine")


def _plan(features, direction, horizon):
    if direction == "LONG":
        return {"entry": 100.0, "stop": 90.0, "t1": 119.0, "t2": 130.0, "rr": 1.9}
    return {"entry": 100.0, "stop": 110.0, "t1": 81.0, "t2": 70.0, "rr": 1.9}


def _candidate(consensus):
    return {
        "symbol": "ETH-USDT",
        "base": "ETH",
        "change_24h_pct": 1.0,
        "spread_bps": 2.0,
        "quote_volume_24h": 1_000_000.0,
        "activity_score": 10.0,
        "market_consensus": consensus,
        "horizons": {"24h": {"score": 2.0, "features": {"1H": {"last": 100.0}}}},
    }


def _trade_signal():
    return {
        "symbol": "ETH-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "strategy_family": "trend",
        "action": "TRADE",
        "evidence_score": 90,
        "reasoning": "AI review requested a trade",
    }


def _validation(approved):
    return SimpleNamespace(
        approved=approved,
        status="LIVE_VALIDATED" if approved else "RESEARCH_ONLY",
        reason="approved" if approved else "not promoted",
        identity={"fingerprint": "a" * 64},
    )


def test_cross_exchange_order_book_stays_research_only_in_production_payload(monkeypatch):
    engine = _load_engine(monkeypatch)
    book = cross_exchange_order_book([
        {"exchange": "okx", "reliable": True, "imbalance_25bps": 0.2},
        {"exchange": "binance", "reliable": True, "imbalance_25bps": -0.1},
    ])
    candidate = _candidate({"reliable": True, "reason": "ok"})
    candidate.update({"derivatives": {}, "order_book": book})

    assert book["reliable"] is True
    assert book["direction_disagreement"] is True
    assert engine.compact(candidate)["order_book"]["research_only"] is True


@pytest.mark.parametrize("reason", ["insufficient_sources", "exchange_price_disagreement"])
def test_unreliable_consensus_forces_wait_for_ranked_opportunity(monkeypatch, reason):
    monkeypatch.setattr(oe, "replace_opportunities", lambda *args: None)
    monkeypatch.setattr(oe, "insert_prediction_ledger", lambda rows: None)
    monkeypatch.setattr(oe, "fetch_resolved_predictions", lambda: [])
    monkeypatch.setattr(oe, "validate_live_strategy", lambda *args: _validation(True))
    monkeypatch.setattr(
        oe,
        "calibration_assessment",
        lambda *args: {"allows_live_action": True},
    )

    result = oe.build_opportunities(
        "scan", [_candidate({"reliable": False, "reason": reason})],
        [_trade_signal()], "BULL_TREND", _plan,
    )

    assert result["24h"][0]["action"] == "WAIT"
    assert reason in result["24h"][0]["reasoning"]


def test_unvalidated_ai_trade_is_wait_in_signal_and_opportunity(monkeypatch):
    engine = _load_engine(monkeypatch)
    candidate = _candidate({"reliable": True, "reason": "ok"})
    saved_signals = []
    monkeypatch.setattr(engine, "build_universe", lambda: [candidate.copy()])
    monkeypatch.setattr(
        engine, "horizon_score",
        lambda symbol, horizon: (2.0, {"1H": {"last": 100.0, "atr": 2.0}}),
    )
    monkeypatch.setattr(engine, "get_derivatives", lambda base: {})
    monkeypatch.setattr(
        engine, "get_order_book_intelligence",
        lambda base: {"research_only": True, "reliable": True, "reason": "ok"},
    )
    monkeypatch.setattr(engine, "latest_news", lambda: [])
    monkeypatch.setattr(engine, "ai_review", lambda *args: {"signals": [_trade_signal()]})
    monkeypatch.setattr(engine, "validate_live_strategy", lambda *args: _validation(False))
    monkeypatch.setattr(engine, "insert_signal", saved_signals.append)
    monkeypatch.setattr(engine, "build_opportunities", lambda *args: {"24h": [], "7d": []})
    monkeypatch.setattr(engine, "record_scan", lambda result: None)

    scan = engine.run_scan()

    monkeypatch.setattr(oe, "replace_opportunities", lambda *args: None)
    monkeypatch.setattr(oe, "insert_prediction_ledger", lambda rows: None)
    monkeypatch.setattr(oe, "fetch_resolved_predictions", lambda: [])
    monkeypatch.setattr(oe, "validate_live_strategy", lambda *args: _validation(False))
    opportunities = oe.build_opportunities(
        "scan", [candidate], [_trade_signal()], "BULL_TREND", _plan,
    )

    assert scan["signals"][0]["action"] == "WAIT"
    assert saved_signals[0]["raw_analysis"]["ai_signal"]["action"] == "TRADE"
    assert opportunities["24h"][0]["action"] == "WAIT"

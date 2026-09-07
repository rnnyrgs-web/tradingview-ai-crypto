import config
import production_validation as pv

# engine constructs its API client at import time; no network call is made in these tests.
config.OPENAI_API_KEY = config.OPENAI_API_KEY or "test-only"

import engine
import opportunity_engine as oe
import pytest


FORBIDDEN_LIVE_ACTIONS = {"TRADE", "BUY", "SELL"}
APPROVED_KEY = ("ETH-USDT", "24h", "trend")


def _risk_plan(features, direction, horizon):
    if direction == "LONG":
        return {"entry": 100.0, "stop": 90.0, "t1": 119.0, "t2": 130.0, "rr": 1.9}
    return {"entry": 100.0, "stop": 110.0, "t1": 81.0, "t2": 70.0, "rr": 1.9}


def _candidate():
    return {
        "symbol": "ETH-USDT",
        "base": "ETH",
        "change_24h_pct": 1.0,
        "spread_bps": 2.0,
        "quote_volume_24h": 1_000_000.0,
        "activity_score": 10.0,
        "horizons": {
            "24h": {"score": 2.0, "features": {"1H": {"last": 100.0}}},
        },
    }


@pytest.mark.parametrize(
    "identity_fields",
    [
        pytest.param({}, id="missing-family"),
        pytest.param({"strategy_family": "unknown_family"}, id="unknown-family"),
        pytest.param({"strategy_family": "tren"}, id="partial-family"),
        pytest.param({"strategy_family": {"name": "trend"}}, id="malformed-family"),
        pytest.param({"symbol": "ETH-US"}, id="partial-symbol"),
        pytest.param({"horizon": "24"}, id="partial-horizon"),
        pytest.param({"strategy_family": None}, id="null-family"),
    ],
)
def test_opportunity_path_fails_closed_for_adversarial_research_identities(
    monkeypatch, identity_fields
):
    """No missing or approximate identity may match an otherwise approved key."""
    monkeypatch.setattr(pv, "LIVE_VALIDATED_STRATEGIES", frozenset({APPROVED_KEY}))
    monkeypatch.setattr(oe, "replace_opportunities", lambda *args: None)

    signal = {
        "symbol": "ETH-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "action": "TRADE",
        "evidence_score": 99,
        "reasoning": "adversarial approval request",
    }
    signal.update(identity_fields)

    result = oe.build_opportunities(
        "scan", [_candidate()], [signal], "BULL_TREND", _risk_plan
    )
    row = result["24h"][0]

    assert row["action"] == "WAIT"
    assert row["action"] not in FORBIDDEN_LIVE_ACTIONS
    assert "RESEARCH_ONLY" in row["reasoning"]


def test_production_engine_fails_closed_for_unapproved_identity_variants(monkeypatch):
    """Engine rows with usable symbol/horizon but bad research identity remain WAIT."""
    monkeypatch.setattr(pv, "LIVE_VALIDATED_STRATEGIES", frozenset({APPROVED_KEY}))
    monkeypatch.setattr(engine, "build_universe", lambda: [_candidate()])
    monkeypatch.setattr(
        engine,
        "horizon_score",
        lambda symbol, horizon: (2.0, {"1H": {"last": 100.0}}),
    )
    monkeypatch.setattr(engine, "get_derivatives", lambda base: {})
    monkeypatch.setattr(engine, "latest_news", lambda: [])
    monkeypatch.setattr(engine, "risk_plan", _risk_plan)
    monkeypatch.setattr(
        engine,
        "build_opportunities",
        lambda *args: {"24h": [], "7d": []},
    )

    identity_variants = [
        {},
        {"strategy_family": "unknown_family"},
        {"strategy_family": "tren"},
        {"strategy_family": {"name": "trend"}},
    ]
    signals = []
    for identity in identity_variants:
        signal = {
            "symbol": "ETH-USDT",
            "horizon": "24h",
            "direction": "LONG",
            "action": "TRADE",
            "evidence_score": 99,
            "reasoning": "adversarial approval request",
        }
        signal.update(identity)
        signals.append(signal)

    monkeypatch.setattr(
        engine,
        "ai_review",
        lambda candidates, regime, news: {"signals": signals},
    )
    saved = []
    monkeypatch.setattr(engine, "insert_signal", saved.append)

    result = engine.run_scan()

    assert result["signals_saved"] == len(identity_variants)
    assert saved
    assert all(row["action"] == "WAIT" for row in saved)
    assert not ({row["action"] for row in saved} & FORBIDDEN_LIVE_ACTIONS)
    assert all(
        row["raw_analysis"]["research_validation"]["status"] == "RESEARCH_ONLY"
        for row in saved
    )
    assert all(
        row["raw_analysis"]["research_validation"]["approved"] is False
        for row in saved
    )

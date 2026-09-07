from copy import deepcopy

import opportunity_engine


def _candidate(symbol, score):
    return {
        "symbol": symbol,
        "activity_score": 0.0,
        "spread_bps": 0.0,
        "horizons": {
            horizon: {"score": score, "features": {"entry": 100.0}}
            for horizon in ("24h", "7d")
        },
    }


def _risk_plan(features, direction, horizon):
    entry = features["entry"]
    risk = 2.0
    sign = 1.0 if direction == "LONG" else -1.0
    return {
        "entry": entry,
        "stop": entry - sign * risk,
        "t1": entry + sign * risk * 1.9,
        "t2": entry + sign * risk * 3.0,
        "rr": 1.9,
    }


def test_untrusted_strategy_registry_cannot_change_live_ranking_or_bypass_wait(monkeypatch):
    """Research registry data is inert unless production explicitly integrates it."""
    monkeypatch.setattr(opportunity_engine, "replace_opportunities", lambda *args: None)

    clean = [
        _candidate("LOW-USDT", 1.0),
        _candidate("TOP-USDT", 4.0),
        _candidate("SHORT-USDT", -3.0),
        _candidate("MID-USDT", 2.0),
    ]
    contaminated = deepcopy(clean)
    contaminated[0]["strategy_registry"] = {
        "registry": [{
            "strategy_family": "trend",
            "status": "RESEARCH_ONLY",
            "weight": 1_000_000,
            "rank_score": 1_000_000,
            "action": "TRADE",
        }]
    }
    contaminated[1]["strategy_registry"] = {
        "registry": [{
            "strategy_family": "unknown_live_strategy",
            "status": "UNKNOWN_STATUS",
            "weight": -1_000_000,
            "action": "TRADE",
        }]
    }
    contaminated[2]["strategy_registry"] = {
        "registry": [None, "ELIGIBLE_OOS", {"status": ["ELIGIBLE_OOS"]}]
    }

    baseline = opportunity_engine.build_opportunities(
        "clean-scan", clean, [], "RANGE_MIXED", _risk_plan
    )
    actual = opportunity_engine.build_opportunities(
        "clean-scan", contaminated, [], "RANGE_MIXED", _risk_plan
    )

    assert actual == baseline
    for horizon in ("24h", "7d"):
        assert [row["symbol"] for row in actual[horizon]] == [
            "TOP-USDT", "SHORT-USDT", "MID-USDT", "LOW-USDT"
        ]
        assert all(row["action"] == "WAIT" for row in actual[horizon])

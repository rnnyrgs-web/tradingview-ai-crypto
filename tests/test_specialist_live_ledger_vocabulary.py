from continuous_specialist_factory import build_specialist_snapshot


def _live_row(**overrides):
    row = {
        "symbol": "BTC-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "market_regime": "BULL_TREND",
        "action_at_forecast": "WAIT",
        "score": 75,
        "correct": False,
        "due_at": "2026-09-08T12:00:00+00:00",
        "resolved_at": "2026-09-08T12:00:00+00:00",
        "directional_return_pct": -1.0,
        "strategy_identity": "strategy-live",
    }
    row.update(overrides)
    return row


def test_live_long_bull_wait_row_reaches_existing_core_specialists():
    reports = build_specialist_snapshot([_live_row()])

    assert reports["buy-errors"]["resolved_rows"] == 1
    assert reports["24h-buy"]["resolved_rows"] == 1
    assert reports["bull-regime"]["resolved_rows"] == 1
    assert reports["wait-quality"]["resolved_rows"] == 1


def test_live_short_bear_row_reaches_sell_and_bear_specialists():
    reports = build_specialist_snapshot([
        _live_row(direction="SHORT", market_regime="BEAR_TREND", action_at_forecast="WAIT")
    ])

    assert reports["sell-errors"]["resolved_rows"] == 1
    assert reports["24h-sell"]["resolved_rows"] == 1
    assert reports["bear-regime"]["resolved_rows"] == 1


def test_live_range_and_transitional_labels_reach_semantic_regime_workers():
    reports = build_specialist_snapshot([
        _live_row(market_regime="RANGE_MIXED"),
        _live_row(market_regime="TRANSITIONAL"),
    ])

    assert reports["sideways-regime"]["resolved_rows"] == 1
    assert reports["unknown-regime"]["resolved_rows"] == 1


def test_legacy_labels_remain_compatible_without_changing_research_authority():
    reports = build_specialist_snapshot([
        _live_row(direction="BUY", market_regime="BULL", action_at_forecast="WAIT")
    ])
    report = reports["buy-errors"]

    assert report["resolved_rows"] == 1
    assert report["research_only"] is True
    assert report["automatic_tuning"] is False
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False

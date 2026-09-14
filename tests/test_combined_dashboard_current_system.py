from combined_dashboard import (
    MIN_FORWARD_CLOSED_TRADES,
    POST_FIX_CUTOVER_UTC,
    _closed_metrics,
    _trade_is_post_fix,
)


def test_post_fix_trade_cutover_is_fail_closed():
    assert _trade_is_post_fix({"opened_at": "2026-09-14T16:32:18Z"}) is False
    assert _trade_is_post_fix({"opened_at": POST_FIX_CUTOVER_UTC}) is True
    assert _trade_is_post_fix({"opened_at": "2026-09-14T16:32:20Z"}) is True
    assert _trade_is_post_fix({}) is False
    assert _trade_is_post_fix({"opened_at": "not-a-date"}) is False


def test_closed_metrics_compute_forward_economics():
    trades = [
        {"closed_at": "2026-09-14T17:00:00Z", "pnl_usd": 100},
        {"closed_at": "2026-09-14T18:00:00Z", "pnl_usd": -50},
    ]
    metrics = _closed_metrics(trades)
    assert metrics["count"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["realized_pnl"] == 50
    assert metrics["win_rate"] == 50
    assert metrics["profit_factor"] == 2
    assert metrics["expectancy"] == 25
    assert metrics["max_drawdown_usd"] == 50


def test_legacy_rows_cannot_contaminate_clean_forward_metrics():
    trades = [
        {
            "opened_at": "2026-09-14T16:00:00Z",
            "closed_at": "2026-09-14T17:00:00Z",
            "pnl_usd": -900,
        },
        {
            "opened_at": "2026-09-14T16:33:00Z",
            "closed_at": "2026-09-14T18:00:00Z",
            "pnl_usd": 100,
        },
    ]
    clean = [trade for trade in trades if _trade_is_post_fix(trade)]
    metrics = _closed_metrics(clean)
    assert metrics["count"] == 1
    assert metrics["realized_pnl"] == 100
    assert metrics["win_rate"] == 100


def test_forward_proof_requires_meaningful_sample():
    assert MIN_FORWARD_CLOSED_TRADES == 30

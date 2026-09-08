from datetime import datetime, timedelta, timezone

from production_risk_gate import (
    assess_execution_risk,
    assess_global_market_risk,
    assess_portfolio_risk,
)


def _healthy_candidate():
    return {
        "change_24h_pct": 2.0,
        "spread_bps": 8.0,
        "market_consensus": {"reliable": True, "reason": "ok"},
        "order_book": {
            "reliable": True,
            "direction_disagreement": False,
            "exchanges": [
                {"live_fill_slippage": {"estimates": [{"quote_notional": 5000.0, "buy": {"complete_fill": True, "slippage_bps_vs_mid": 4.0}, "sell": {"complete_fill": True, "slippage_bps_vs_mid": 4.0}}]}},
                {"live_fill_slippage": {"estimates": [{"quote_notional": 5000.0, "buy": {"complete_fill": True, "slippage_bps_vs_mid": 6.0}, "sell": {"complete_fill": True, "slippage_bps_vs_mid": 6.0}}]}},
            ],
        },
    }


def _healthy_health():
    return {
        "last_scan": {
            "at": datetime.now(timezone.utc).isoformat(),
            "ok": True,
            "universe_count": 50,
            "deep_scanned": 30,
            "scan_error_count": 1,
        },
        "recent_error_count": 0,
    }


def test_healthy_execution_preserves_existing_authority():
    decision = assess_execution_risk(_healthy_candidate(), "LONG")
    assert not decision.blocked
    assert decision.allows_existing_authority


def test_bad_execution_forces_wait():
    row = _healthy_candidate()
    row["spread_bps"] = 80.0
    row["order_book"]["direction_disagreement"] = True
    decision = assess_execution_risk(row, "LONG")
    assert decision.blocked
    assert "spread_too_wide" in decision.reasons
    assert "cross_exchange_book_disagreement" in decision.reasons


def test_incomplete_visible_depth_blocks_execution():
    row = _healthy_candidate()
    for exchange in row["order_book"]["exchanges"]:
        exchange["live_fill_slippage"]["estimates"][0]["buy"] = {"complete_fill": False, "slippage_bps_vs_mid": 0.0}
    decision = assess_execution_risk(row, "LONG")
    assert decision.blocked
    assert "insufficient_visible_depth" in decision.reasons


def test_broad_volatility_and_liquidity_stress_force_global_wait():
    rows = []
    for _ in range(10):
        row = _healthy_candidate()
        row["change_24h_pct"] = 30.0
        row["spread_bps"] = 150.0
        rows.append(row)
    decision = assess_global_market_risk(rows)
    assert decision.blocked
    assert "broad_market_volatility_shock" in decision.reasons
    assert "broad_liquidity_stress" in decision.reasons


def test_repeated_cross_exchange_disagreement_forces_global_wait():
    rows = [_healthy_candidate() for _ in range(5)]
    rows[0]["market_consensus"] = {"reliable": False, "reason": "exchange_price_disagreement"}
    rows[1]["market_consensus"] = {"reliable": False, "reason": "exchange_price_disagreement"}
    decision = assess_global_market_risk(rows)
    assert decision.blocked
    assert "cross_exchange_data_instability" in decision.reasons


def test_unhealthy_system_forces_global_wait():
    health = _healthy_health()
    health["last_scan"]["ok"] = False
    health["recent_error_count"] = 11
    decision = assess_global_market_risk([], health)
    assert decision.blocked
    assert "production_scan_unhealthy" in decision.reasons
    assert "repeated_system_errors" in decision.reasons


def test_corrupt_market_snapshot_forces_global_wait():
    rows = [_healthy_candidate() for _ in range(10)]
    for row in rows[:4]:
        row["spread_bps"] = float("nan")
        row["change_24h_pct"] = None
        row.pop("market_consensus", None)
    decision = assess_global_market_risk(rows, _healthy_health())
    assert decision.blocked
    assert "incomplete_or_corrupt_market_snapshot" in decision.reasons


def test_stale_health_snapshot_forces_global_wait():
    health = _healthy_health()
    health["last_scan"]["at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    decision = assess_global_market_risk([_healthy_candidate() for _ in range(5)], health)
    assert decision.blocked
    assert "stale_system_health" in decision.reasons


def test_scan_coverage_collapse_and_failures_force_wait():
    health = _healthy_health()
    health["last_scan"].update({"universe_count": 100, "deep_scanned": 20, "scan_error_count": 20})
    decision = assess_global_market_risk([_healthy_candidate() for _ in range(5)], health)
    assert decision.blocked
    assert "deep_scan_coverage_collapse" in decision.reasons
    assert "excessive_scan_failures" in decision.reasons


def test_malformed_health_fails_closed():
    health = _healthy_health()
    health["recent_error_count"] = "unknown"
    decision = assess_global_market_risk([_healthy_candidate() for _ in range(5)], health)
    assert decision.blocked
    assert "malformed_system_health" in decision.reasons


def test_portfolio_drawdown_and_loss_streak_block_new_positions():
    account = {"initial_cash": 100000.0, "equity": 89000.0, "peak_equity": 100000.0, "max_drawdown_pct": 11.0}
    stats = {"consecutive_losses": 4}
    decision = assess_portfolio_risk(account, [], stats)
    assert decision.blocked
    assert "portfolio_drawdown_limit" in decision.reasons
    assert "repeated_loss_streak" in decision.reasons


def test_directional_concentration_blocks_new_positions():
    account = {"initial_cash": 100000.0, "equity": 100000.0, "peak_equity": 100000.0, "max_drawdown_pct": 0.0}
    trades = [{"direction": "LONG"} for _ in range(4)]
    decision = assess_portfolio_risk(account, trades, {"consecutive_losses": 0})
    assert decision.blocked
    assert "correlated_directional_concentration" in decision.reasons


def test_malformed_portfolio_state_fails_closed():
    decision = assess_portfolio_risk(
        {"initial_cash": 100000.0, "equity": float("nan"), "peak_equity": 100000.0, "max_drawdown_pct": 0.0},
        [],
        {},
    )
    assert decision.blocked
    assert decision.reasons == ("malformed_portfolio_state",)

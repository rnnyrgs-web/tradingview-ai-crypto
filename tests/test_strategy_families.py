from strategy_families import (
    STRATEGY_FAMILIES,
    _quality_gate,
    _signal_breakout,
    _signal_volatility_expansion,
)


def metrics(trades, avg, pf, dd=5.0):
    return {
        "trades": trades,
        "win_rate_pct": 50.0,
        "avg_trade_pct": avg,
        "sum_net_returns_pct": avg * trades,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
    }


def test_expected_strategy_families_present():
    assert set(STRATEGY_FAMILIES) == {
        "trend",
        "breakout",
        "momentum",
        "mean_reversion",
        "volatility_expansion",
        "relative_strength",
    }


def test_quality_gate_passes_robust_oos_candidate():
    gate = _quality_gate(
        metrics(30, 0.10, 1.30),
        metrics(12, 0.08, 1.20),
        metrics(12, 0.09, 1.25),
    )
    assert gate["passed"] is True
    assert gate["eligible_for_live_ensemble"] is True
    assert gate["reasons"] == []


def test_quality_gate_rejects_negative_holdout():
    gate = _quality_gate(
        metrics(30, 0.10, 1.30),
        metrics(12, 0.08, 1.20),
        metrics(12, -0.03, 0.90),
    )
    assert gate["passed"] is False
    assert gate["eligible_for_live_ensemble"] is False
    assert "holdout_expectancy<=0" in gate["reasons"]
    assert "holdout_pf<1.10" in gate["reasons"]


def _candle(price=100.0):
    return {
        "open": price,
        "high": price + 1.0,
        "low": price - 1.0,
        "close": price,
        "volume": 100.0,
    }


def test_breakout_and_volatility_signals_fail_closed_on_nan_ohlcv():
    candles = [_candle() for _ in range(40)]
    candles[39]["close"] = float("nan")

    assert _signal_breakout(candles, 39, None) is None
    assert _signal_volatility_expansion(candles, 39, None) is None

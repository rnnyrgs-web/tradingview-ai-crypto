import pytest

from config import BACKTEST_COST_BPS
from strategy_families import (
    STRATEGY_FAMILIES,
    _quality_gate,
    _signal_mean_reversion,
    _simulate,
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


def _candle(ts, close, spread=1.0, open_price=None):
    return {
        "ts": ts,
        "open": close if open_price is None else open_price,
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": 100.0,
    }


def test_mean_reversion_signal_does_not_read_future_candles():
    candles = [_candle(i, 100.0) for i in range(40)]
    candles.append(_candle(40, 90.0, spread=1.0, open_price=90.0))
    assert _signal_mean_reversion(candles, 40, None) == "LONG"

    candles.append(_candle(41, 1.0, spread=50.0, open_price=1.0))
    assert _signal_mean_reversion(candles, 40, None) == "LONG"


def test_strategy_simulation_enters_at_next_bar_open(monkeypatch):
    candles = [_candle(i, 100.0) for i in range(70)]
    candles.append(_candle(70, 100.0))
    candles.append(_candle(71, 110.0, spread=0.5, open_price=110.0))
    candles.extend(_candle(i, 110.0, spread=0.5) for i in range(72, 100))

    def signal_at_index(candles, i, _benchmark):
        return "LONG" if i == 70 else None

    monkeypatch.setitem(
        __import__("strategy_families").SIGNAL_FUNCTIONS,
        "mean_reversion",
        signal_at_index,
    )
    returns = _simulate(candles, "15m", "mean_reversion")

    assert len(returns) == 1
    # The signal candle closes at 100, but the modeled fill is the next open at 110.
    assert returns[0] == pytest.approx(-BACKTEST_COST_BPS / 100.0)

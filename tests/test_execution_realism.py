import backtest


def _history(count=140):
    rows = []
    for i in range(count):
        rows.append({
            "ts": i,
            "open": 100.0,
            "high": 100.2,
            "low": 99.8,
            "close": 100.0,
            "volume": 1000.0,
            "quote_volume": 100000.0,
        })
    return rows


def test_execution_cost_scenarios_are_monotonic_and_bounded():
    assert backtest.execution_cost_scenarios(12) == (12.0, 18.0, 24.0, 36.0)
    assert backtest.execution_cost_scenarios(-1) == (0.0,)


def test_higher_cost_never_improves_same_trade_path(monkeypatch):
    hist = _history(150)
    monkeypatch.setattr(
        backtest,
        "_features_at",
        lambda _hist, _i: {"score": 3.0, "atr": 1.0},
    )
    base = backtest._score_history(hist, "15m", 2.25, 12)
    stressed = backtest._score_history(hist, "15m", 2.25, 36)
    assert len(base) == len(stressed) > 0
    for normal, expensive in zip(base, stressed):
        assert expensive < normal
        assert round(normal - expensive, 10) == 0.24


def test_summary_reports_drawdown_and_net_returns():
    summary = backtest.summarize_returns([1.0, -0.5, 0.25])
    assert summary["trades"] == 3
    assert summary["win_rate_pct"] == 66.67
    assert summary["sum_net_returns_pct"] == 0.75
    assert summary["max_drawdown_pct"] > 0

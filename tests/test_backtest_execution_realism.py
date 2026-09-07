import pytest

import backtest


def _history(count=140):
    return [{
        "ts": i,
        "open": 100.0,
        "high": 100.2,
        "low": 99.8,
        "close": 100.0,
        "volume": 1000.0,
        "quote_volume": 100000.0,
    } for i in range(count)]


def test_execution_cost_stress_refuses_unavailable_or_non_chronological_timestamps():
    missing = _history()
    del missing[110]["ts"]
    with pytest.raises(ValueError, match="Timestamp data unavailable"):
        backtest._score_history(missing, "15m", 2.25, 12)

    out_of_order = _history()
    out_of_order[110]["ts"] = out_of_order[109]["ts"]
    with pytest.raises(ValueError, match="strictly increasing"):
        backtest._score_history(out_of_order, "15m", 2.25, 12)


def test_execution_cost_stress_keeps_same_timestamp_safe_trade_path(monkeypatch):
    monkeypatch.setattr(backtest, "_features_at", lambda _hist, _i: {"score": 3.0, "atr": 1.0})
    hist = _history(150)
    base = backtest._score_history(hist, "15m", 2.25, 12)
    stressed = backtest._score_history(hist, "15m", 2.25, 36)
    assert len(base) == len(stressed) > 0
    assert all(round(normal - expensive, 10) == 0.24 for normal, expensive in zip(base, stressed))

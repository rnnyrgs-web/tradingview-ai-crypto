from datetime import date, timedelta
import math

import pytest

from big_move_feature_derivations import (
    compute_btc_regime,
    compute_return_30d,
    compute_volatility_30d,
    value_matches,
)


def _rows(decision="2024-04-01", days=100, close_fn=None):
    decision_date = date.fromisoformat(decision)
    rows = []
    for offset in range(days, 0, -1):
        d = decision_date - timedelta(days=offset)
        index = days - offset
        close = close_fn(index) if close_fn else 100 + index
        rows.append({"date": d.isoformat(), "close": str(close), "quote_volume_usd": "10000000"})
    return rows


def test_return_30d_uses_exact_day_minus_31_to_day_minus_1_window():
    rows = _rows(days=40, close_fn=lambda i: 100 + i)
    value = compute_return_30d(rows, decision_at="2024-04-01T00:00:00Z")
    # 40-row series: day -31 has index 9, day -1 has index 39.
    assert value == pytest.approx(139 / 109 - 1, rel=1e-12)


def test_volatility_is_sample_std_of_30_log_returns_annualized_365():
    ratio = 1.01
    rows = _rows(days=40, close_fn=lambda i: 100 * (ratio**i))
    value = compute_volatility_30d(rows, decision_at="2024-04-01T00:00:00Z")
    assert value == pytest.approx(0.0, abs=1e-12)


def test_btc_regime_rule_is_deterministic():
    rising = _rows(days=90, close_fn=lambda i: 100 + i)
    assert compute_btc_regime(rising, decision_at="2024-04-01T00:00:00Z") == "RISK_ON"

    falling = _rows(days=90, close_fn=lambda i: 200 - i)
    assert compute_btc_regime(falling, decision_at="2024-04-01T00:00:00Z") == "RISK_OFF"

    mixed = _rows(days=90, close_fn=lambda i: 100 if i < 59 else 90 + (i - 59) * 0.1)
    assert compute_btc_regime(mixed, decision_at="2024-04-01T00:00:00Z") == "MIXED"


def test_missing_required_daily_bar_fails_closed():
    rows = _rows(days=40)
    rows = [row for row in rows if row["date"] != "2024-03-15"]
    with pytest.raises(ValueError, match="missing completed daily bars"):
        compute_return_30d(rows, decision_at="2024-04-01T00:00:00Z")


def test_nonpositive_close_is_rejected():
    rows = _rows(days=40)
    rows[-2]["close"] = "0"
    with pytest.raises(ValueError, match="finite and > 0"):
        compute_volatility_30d(rows, decision_at="2024-04-01T00:00:00Z")


def test_value_match_is_strict_and_rejects_nonfinite_or_boolean():
    assert value_matches("0.125", 0.125)
    assert not value_matches("0.126", 0.125)
    assert not value_matches(float("nan"), 0.125)
    assert not value_matches(True, 1.0)

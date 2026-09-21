"""Frozen outcome-blind feature derivations for 2x Cohort 001.

Inputs to these functions must already be value-bound to retained pre-cutoff market
archives (for example by `big_move_binance_archive_binding`). This module contains no
source fetching and no outcome access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import math
from statistics import stdev
from typing import Any

UTC = timezone.utc
RETURN_WINDOW_DAYS = 30
VOLATILITY_WINDOW_DAYS = 30
VOLATILITY_ANNUALIZATION_DAYS = 365
REGIME_SMA_DAYS = 90
REGIME_RETURN_DAYS = 30

RETURN_TRANSFORM = {
    "transform_id": "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
    "transform_version": "2",
    "metric": "return_30d",
    "window_days": 30,
    "method": "simple_close_to_close",
    "completed_daily_bars_only": True,
}
VOLATILITY_TRANSFORM = {
    "transform_id": "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
    "transform_version": "2",
    "metric": "volatility_30d",
    "window_days": 30,
    "method": "sample_std_daily_log_returns",
    "annualization_days": 365,
    "completed_daily_bars_only": True,
}
REGIME_TRANSFORM = {
    "transform_id": "DERIVED_BTC_MARKET_REGIME_V1",
    "transform_version": "2",
    "return_lookback_days": 30,
    "sma_days": 90,
    "rule": "RISK_ON if r30>0 and close>=sma90; RISK_OFF if r30<0 and close<sma90; otherwise MIXED",
    "completed_daily_bars_only": True,
}


def _utc(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _close(row: dict[str, Any], *, field: str) -> float:
    try:
        value = Decimal(str(row.get("close")))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{field}.close must be decimal") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field}.close must be finite and > 0")
    return float(value)


def _exact_daily_window(rows: list[dict[str, Any]], *, decision_at: str, days: int) -> list[dict[str, Any]]:
    decision = _utc(decision_at, field="decision_at")
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    by_date: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"rows[{index}] must be an object")
        date = row.get("date")
        if not isinstance(date, str) or not date:
            raise ValueError(f"rows[{index}].date missing")
        if date in by_date:
            raise ValueError("daily rows contain duplicate date")
        _close(row, field=f"rows[{index}]")
        by_date[date] = row
    expected_dates = [
        (decision.date() - timedelta(days=offset)).isoformat()
        for offset in range(days, 0, -1)
    ]
    missing = [date for date in expected_dates if date not in by_date]
    if missing:
        raise ValueError(f"missing completed daily bars for frozen window: {missing[0]}")
    return [by_date[date] for date in expected_dates]


def compute_return_30d(rows: list[dict[str, Any]], *, decision_at: str) -> float:
    """Simple 30-day close-to-close return using day -31 and day -1 closes."""
    window = _exact_daily_window(rows, decision_at=decision_at, days=RETURN_WINDOW_DAYS + 1)
    first = _close(window[0], field="return.first")
    last = _close(window[-1], field="return.last")
    return last / first - 1.0


def compute_volatility_30d(rows: list[dict[str, Any]], *, decision_at: str) -> float:
    """Annualized sample std.dev. of 30 daily log returns from 31 completed closes."""
    window = _exact_daily_window(rows, decision_at=decision_at, days=VOLATILITY_WINDOW_DAYS + 1)
    closes = [_close(row, field=f"volatility.rows[{index}]") for index, row in enumerate(window)]
    log_returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))]
    if len(log_returns) != VOLATILITY_WINDOW_DAYS:
        raise ValueError("volatility window must contain exactly 30 daily returns")
    return stdev(log_returns) * math.sqrt(VOLATILITY_ANNUALIZATION_DAYS)


def compute_btc_regime(rows: list[dict[str, Any]], *, decision_at: str) -> str:
    """Frozen BTC regime from 90 completed daily closes; no future bar is eligible."""
    window = _exact_daily_window(rows, decision_at=decision_at, days=REGIME_SMA_DAYS)
    closes = [_close(row, field=f"regime.rows[{index}]") for index, row in enumerate(window)]
    last = closes[-1]
    prior_30 = closes[-(REGIME_RETURN_DAYS + 1)]
    r30 = last / prior_30 - 1.0
    sma90 = sum(closes) / len(closes)
    if r30 > 0 and last >= sma90:
        return "RISK_ON"
    if r30 < 0 and last < sma90:
        return "RISK_OFF"
    return "MIXED"


def value_matches(claimed: Any, computed: float, *, rel_tol: float = 1e-12, abs_tol: float = 1e-12) -> bool:
    if isinstance(claimed, bool):
        return False
    try:
        value = float(claimed)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and math.isclose(value, computed, rel_tol=rel_tol, abs_tol=abs_tol)

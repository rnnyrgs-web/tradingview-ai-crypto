"""Deterministic source-native liquidity transform for Cohort-001.

This module implements the outcome-blind numeric/unit boundary frozen in #721.
It deliberately has *no* source-authenticity authority: callers must first verify
Binance archive/checksum/provider provenance through the canonical authenticity
path. Passing this transform therefore proves only deterministic quote-native
liquidity semantics, never provider origin, historical membership, a 2x label,
strict tradability, forecast authority, or broker authority.

Binance spot kline field 7 is quote-asset volume. For the frozen Cohort-001
universe the quote asset is exactly USDT. USDT values are never relabelled USD.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from statistics import median
from typing import Any

SCHEMA = "binance_spot_daily_kline_rows.v2"
TRANSFORM_ID = "TRAILING_30D_MEDIAN_QUOTE_ASSET_VOLUME_V2"
TRANSFORM_VERSION = "2"
VENUE = "BINANCE_SPOT"
QUOTE_ASSET = "USDT"
WINDOW_DAYS = 30
THRESHOLD_QUOTE_ASSET = 10_000_000.0


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def frozen_parameters() -> dict[str, Any]:
    """Return the exact scientific identity of the V2 transform."""
    return {
        "window_days": WINDOW_DAYS,
        "statistic": "median",
        "measure": "quote_asset_volume",
        "quote_asset": QUOTE_ASSET,
        "unit": QUOTE_ASSET,
        "bar_cadence": "1d",
        "calendar": "UTC",
        "completed_daily_bars_only": True,
        "decision_boundary": "STRICTLY_BEFORE_DECISION_AT",
    }


def compute_trailing_quote_asset_liquidity(
    normalized_artifact: dict[str, Any],
    *,
    decision_at: str,
    expected_symbol: str,
    expected_quote_asset: str = QUOTE_ASSET,
) -> float:
    """Compute the frozen 30d median in provider-native quote-asset units.

    ``normalized_artifact`` must already have been bound to authenticated Binance
    source bytes by the upstream provenance layer. This function intentionally
    refuses any USD-labelled alias and recomputes from exactly the previous 30
    completed UTC calendar dates.
    """
    if not isinstance(normalized_artifact, dict):
        raise ValueError("normalized artifact must be an object")
    if normalized_artifact.get("schema") != SCHEMA:
        raise ValueError(f"normalized artifact must use {SCHEMA}")
    if normalized_artifact.get("source_id") != "BINANCE_PUBLIC_DATA_SPOT_RAW":
        raise ValueError("normalized artifact source_id mismatch")
    if normalized_artifact.get("venue_symbol") != expected_symbol:
        raise ValueError("normalized artifact venue_symbol mismatch")
    if expected_quote_asset != QUOTE_ASSET:
        raise ValueError("Cohort-001 V2 quote asset must be exactly USDT")
    if not isinstance(expected_symbol, str) or not expected_symbol.endswith(expected_quote_asset):
        raise ValueError("venue_symbol is not bound to the frozen USDT quote-asset universe")

    decision = _utc(decision_at, field="decision_at")
    expected_dates = {
        (decision.date() - timedelta(days=offset)).isoformat()
        for offset in range(1, WINDOW_DAYS + 1)
    }

    rows = normalized_artifact.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("normalized artifact rows missing")

    by_date: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("normalized row malformed")
        if "quote_volume_usd" in row:
            raise ValueError("USD-labelled quote-volume alias is forbidden in V2")
        date = row.get("date")
        if not isinstance(date, str):
            raise ValueError("normalized row date missing")
        if date in by_date:
            raise ValueError("duplicate UTC date in quote-native liquidity input")
        try:
            row_date = datetime.fromisoformat(date).date()
        except ValueError as exc:
            raise ValueError("normalized row date invalid") from exc
        if row_date >= decision.date():
            raise ValueError("quote-native liquidity input includes decision/post-decision date")
        try:
            volume = float(row.get("quote_asset_volume"))
        except (TypeError, ValueError) as exc:
            raise ValueError("quote_asset_volume must be numeric") from exc
        if not math.isfinite(volume) or volume < 0:
            raise ValueError("quote_asset_volume must be finite and nonnegative")
        by_date[date] = volume

    if set(by_date) != expected_dates:
        missing = sorted(expected_dates - set(by_date))
        extra = sorted(set(by_date) - expected_dates)
        raise ValueError(
            "quote-native liquidity requires exactly the previous 30 completed UTC dates; "
            f"missing={missing[:3]} extra={extra[:3]}"
        )

    return float(median(by_date[date] for date in sorted(expected_dates)))


def validate_derived_record(
    record: dict[str, Any],
    normalized_artifact: dict[str, Any],
    *,
    decision_at: str,
    expected_symbol: str,
) -> float:
    """Validate a retained V2 derived record against deterministic recomputation."""
    if not isinstance(record, dict):
        raise ValueError("liquidity record must be an object")
    if record.get("source_id") != TRANSFORM_ID:
        raise ValueError("liquidity source_id/transform identity mismatch")
    if record.get("unit") != QUOTE_ASSET:
        raise ValueError("liquidity unit must be explicit USDT")
    if "liquidity_usd" in record or "quote_volume_usd" in record:
        raise ValueError("USD-labelled semantics are forbidden in quote-native V2")

    derivation = record.get("derivation")
    if not isinstance(derivation, dict):
        raise ValueError("liquidity derivation missing")
    if derivation.get("transform_id") != TRANSFORM_ID:
        raise ValueError("liquidity derivation transform_id mismatch")
    if derivation.get("transform_version") != TRANSFORM_VERSION:
        raise ValueError("liquidity derivation transform_version mismatch")
    if derivation.get("parameters") != frozen_parameters():
        raise ValueError("liquidity derivation parameters violate frozen V2 semantics")

    computed = compute_trailing_quote_asset_liquidity(
        normalized_artifact,
        decision_at=decision_at,
        expected_symbol=expected_symbol,
    )
    try:
        claimed = float(record.get("value"))
    except (TypeError, ValueError) as exc:
        raise ValueError("liquidity record value must be numeric") from exc
    if not math.isfinite(claimed):
        raise ValueError("liquidity record value must be finite")
    if not math.isclose(claimed, computed, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("liquidity record value does not equal deterministic 30d median")
    return computed


def passes_coarse_liquidity_gate(value: Any, *, unit: str) -> bool:
    """Apply the frozen 10M-USDT coarse screen; this is not strict tradability."""
    if unit != QUOTE_ASSET:
        raise ValueError("coarse liquidity gate requires explicit USDT unit")
    if isinstance(value, bool):
        raise ValueError("liquidity value must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("liquidity value must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("liquidity value must be finite and nonnegative")
    return number >= THRESHOLD_QUOTE_ASSET

"""Outcome-blind Kraken 60m timestamp semantics for EXT-ETH-SESSION-REVERSAL-001-v1.

This module freezes only time/boundary semantics. It does not fetch provider bytes,
resolve a Kraken pair/member, normalize OHLCV prices, compute strategy returns, open
protected evidence, connect a broker, or grant screening/trading authority.

The key PIT rule is that a Kraken candle timestamp identifies INTERVAL BEGIN.
Therefore the close of a 60-minute row labelled ``t`` is not available until ``t+1h``.
The pinned external replication computes close-to-close returns on those labels before
grouping labels 05..16 as daytime and 17..04 as nighttime.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

UTC = timezone.utc
INTERVAL = timedelta(hours=1)
DAY_START_HOUR = 5
DAY_END_HOUR = 17
REQUIRED_START = datetime(2026, 1, 1, 4, tzinfo=UTC)
REQUIRED_END = datetime(2026, 6, 30, 16, tzinfo=UTC)
SEALED_HISTORICAL_TAIL_START = datetime(2026, 7, 1, 0, tzinfo=UTC)
GENUINE_FORWARD_SHADOW_START = datetime(2026, 9, 24, 17, tzinfo=UTC)

CONTRACT_PATH = (
    "orchestration/external_replication/"
    "ext_eth_session_reversal_001_kraken_time_semantics_v1.json"
)
CONTRACT_ID = "EXT-ETH-SESSION-REVERSAL-001-v1-KRAKEN-TIME-SEMANTICS-v1"
CONTRACT_ARTIFACT_SHA256 = "3a60bc76d98b47e4c381f11a95c8dfea7b1252569197b22b38df340a35bdc91b"


def _canonical_artifact_digest(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_contract(repo_root: str | Path | None = None) -> dict:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    payload = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    if payload.get("preflight_id") != CONTRACT_ID:
        raise ValueError("Kraken time-semantics contract identity mismatch")
    if payload.get("artifact_sha256") != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("Kraken time-semantics artifact identity mismatch")
    if _canonical_artifact_digest(payload) != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("Kraken time-semantics self-digest mismatch")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("Kraken time-semantics authority block missing")
    forbidden_true = (
        "provider_bytes_authenticated",
        "pair_resolution_authority",
        "timestamp_semantics_runtime_authority",
        "normalized_rows_authority",
        "stage_1_screen_authority",
        "baseline_or_control_pnl_authority",
        "retrospective_holdout_authority",
        "genuine_forward_shadow_authority",
        "profitability_claim_authority",
        "promotion_authority",
        "broker_connected",
        "live_trading",
        "trade_authority",
    )
    if any(authority.get(key) is not False for key in forbidden_true):
        raise ValueError("Kraken time-semantics contract escalated authority")
    if authority.get("timestamp_semantics_frozen_for_review") is not True:
        raise ValueError("timestamp semantics must remain frozen-for-review only")
    return payload


def require_hour_aligned_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    normalized = value.astimezone(UTC)
    if any((normalized.minute, normalized.second, normalized.microsecond)):
        raise ValueError("timestamp must align exactly to a whole UTC hour")
    return normalized


def close_available_at(interval_begin: datetime) -> datetime:
    """Earliest PIT availability of a 60m row close."""
    return require_hour_aligned_utc(interval_begin) + INTERVAL


def boundary_source_interval_begin(boundary: datetime) -> datetime:
    """Return the completed 60m interval whose close is available at boundary."""
    return require_hour_aligned_utc(boundary) - INTERVAL


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=UTC)


def day_interval_begins(trading_date: date) -> tuple[datetime, ...]:
    base = _utc_midnight(trading_date)
    return tuple(base + timedelta(hours=hour) for hour in range(5, 17))


def night_interval_begins(trading_date: date) -> tuple[datetime, ...]:
    base = _utc_midnight(trading_date)
    prior = base - timedelta(days=1)
    return tuple(
        [prior + timedelta(hours=hour) for hour in range(17, 24)]
        + [base + timedelta(hours=hour) for hour in range(0, 5)]
    )


def source_bar_return_boundaries(interval_begin: datetime) -> tuple[datetime, datetime]:
    """Economic boundaries of source-style close.pct_change() labelled at t.

    A row labelled t contains the close realized at t+1h. Its previous row contains
    the close realized at t. Therefore the return labelled t spans [t, t+1h].
    """
    start = require_hour_aligned_utc(interval_begin)
    return start, start + INTERVAL


def day_economic_boundaries(trading_date: date) -> tuple[datetime, datetime]:
    labels = day_interval_begins(trading_date)
    return source_bar_return_boundaries(labels[0])[0], close_available_at(labels[-1])


def night_economic_boundaries(trading_date: date) -> tuple[datetime, datetime]:
    labels = night_interval_begins(trading_date)
    return source_bar_return_boundaries(labels[0])[0], close_available_at(labels[-1])


def previous_day_signal_available_at(trading_date: date) -> datetime:
    """Availability of the previous completed daytime return used at D 05:00."""
    previous = trading_date - timedelta(days=1)
    return close_available_at(day_interval_begins(previous)[-1])


def day_decision_time(trading_date: date) -> datetime:
    return _utc_midnight(trading_date) + timedelta(hours=DAY_START_HOUR)


def day_exit_night_entry_time(trading_date: date) -> datetime:
    return _utc_midnight(trading_date) + timedelta(hours=DAY_END_HOUR)


def required_interval_begins() -> tuple[datetime, ...]:
    """All permitted hourly interval-begin labels in the frozen normalized window."""
    values: list[datetime] = []
    current = REQUIRED_START
    while current <= REQUIRED_END:
        values.append(current)
        current += INTERVAL
    return tuple(values)


def missing_required_interval_begins(
    observed: Iterable[datetime],
) -> tuple[datetime, ...]:
    """Fail-closed gap detector; never interpolates or shifts timestamps."""
    normalized: list[datetime] = [require_hour_aligned_utc(item) for item in observed]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate Kraken interval_begin timestamp")
    if any(item < REQUIRED_START or item > REQUIRED_END for item in normalized):
        raise ValueError("observed interval_begin escapes frozen normalized window")
    expected = set(required_interval_begins())
    return tuple(sorted(expected.difference(normalized)))


def assert_no_future_close_at_decisions(trading_date: date) -> None:
    """Mechanical PIT proof for the two execution boundaries."""
    day_boundary = day_decision_time(trading_date)
    evening_boundary = day_exit_night_entry_time(trading_date)

    if close_available_at(boundary_source_interval_begin(day_boundary)) != day_boundary:
        raise AssertionError("05:00 boundary price is not a completed-row close")
    if close_available_at(boundary_source_interval_begin(evening_boundary)) != evening_boundary:
        raise AssertionError("17:00 boundary price is not a completed-row close")

    signal_ready = previous_day_signal_available_at(trading_date)
    if not signal_ready < day_boundary:
        raise AssertionError("previous daytime signal is not PIT-available before 05:00")

    if close_available_at(day_boundary) <= day_boundary:
        raise AssertionError("05:00-labelled candle close was treated as known at 05:00")
    if close_available_at(evening_boundary) <= evening_boundary:
        raise AssertionError("17:00-labelled candle close was treated as known at 17:00")


def frozen_window_is_contained() -> bool:
    return (
        REQUIRED_START < REQUIRED_END < SEALED_HISTORICAL_TAIL_START
        and REQUIRED_END < GENUINE_FORWARD_SHADOW_START
    )

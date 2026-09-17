"""Fail-closed certification for deterministic research dataset manifests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from typing import Any


REQUIRED_FIELDS = (
    "dataset_id",
    "source",
    "venue",
    "symbol",
    "timezone",
    "start_timestamp",
    "end_timestamp",
    "fields",
    "missing_periods",
    "duplicate_timestamps",
    "out_of_order_records",
    "impossible_ohlc_records",
    "stale_records",
    "future_universe_membership",
    "future_feature_use",
    "point_in_time_universe",
    "content_sha256",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _count(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number < 0 or int(number) != number:
        return None
    return int(number)


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def certify_dataset_manifest(manifest: dict) -> dict:
    """Return a deterministic certification verdict for an exact dataset snapshot."""
    if not isinstance(manifest, dict):
        return {
            "certified": False,
            "dataset_id": None,
            "dataset_sha256": "",
            "checks": {},
            "failures": ["manifest_not_object"],
        }

    failures: list[str] = []
    checks: dict[str, bool] = {}
    missing = [field for field in REQUIRED_FIELDS if field not in manifest]
    failures.extend(f"missing:{field}" for field in missing)

    timezone_ok = str(manifest.get("timezone") or "").upper() == "UTC"
    checks["timezone_utc"] = timezone_ok
    if not timezone_ok:
        failures.append("timezone_not_utc")

    point_in_time_ok = manifest.get("point_in_time_universe") is True
    checks["point_in_time_universe"] = point_in_time_ok
    if not point_in_time_ok:
        failures.append("point_in_time_universe_missing")

    content_hash_ok = bool(str(manifest.get("content_sha256") or "").strip())
    checks["content_hash_present"] = content_hash_ok
    if not content_hash_ok:
        failures.append("content_sha256_missing")

    fields = manifest.get("fields")
    fields_ok = isinstance(fields, list) and all(
        field in fields for field in ("open", "high", "low", "close", "volume")
    )
    checks["required_ohlcv_fields"] = fields_ok
    if not fields_ok:
        failures.append("required_ohlcv_fields_missing")

    missing_periods = manifest.get("missing_periods")
    missing_periods_ok = isinstance(missing_periods, list) and not missing_periods
    checks["no_missing_periods"] = missing_periods_ok
    if not missing_periods_ok:
        failures.append("missing_periods")

    for field, failure_name in (
        ("duplicate_timestamps", "duplicate_timestamps"),
        ("out_of_order_records", "out_of_order_records"),
        ("impossible_ohlc_records", "impossible_ohlc_records"),
        ("stale_records", "stale_records"),
    ):
        count = _count(manifest.get(field))
        ok = count == 0
        checks[f"no_{field}"] = ok
        if not ok:
            failures.append(failure_name)

    future_membership_ok = manifest.get("future_universe_membership") is False
    checks["no_future_universe_membership"] = future_membership_ok
    if not future_membership_ok:
        failures.append("future_universe_membership")

    future_feature_ok = manifest.get("future_feature_use") is False
    checks["no_future_feature_use"] = future_feature_ok
    if not future_feature_ok:
        failures.append("future_feature_use")

    start = _parse_timestamp(manifest.get("start_timestamp"))
    end = _parse_timestamp(manifest.get("end_timestamp"))
    chronology_ok = bool(
        start is not None
        and end is not None
        and start.tzinfo is not None
        and end.tzinfo is not None
        and start <= end
    )
    checks["timestamp_range_valid"] = chronology_ok
    if not chronology_ok:
        failures.append("invalid_timestamp_range")

    text_identity_ok = all(
        str(manifest.get(field) or "").strip()
        for field in ("dataset_id", "source", "venue", "symbol")
    )
    checks["dataset_identity_present"] = bool(text_identity_ok)
    if not text_identity_ok:
        failures.append("dataset_identity_missing")

    try:
        dataset_sha = hashlib.sha256(_canonical_bytes(manifest)).hexdigest()
    except (TypeError, ValueError):
        dataset_sha = ""
        failures.append("manifest_not_canonicalizable")

    # Preserve one occurrence per failure so downstream policy remains deterministic.
    unique_failures = list(dict.fromkeys(failures))
    return {
        "certified": not unique_failures,
        "dataset_id": str(manifest.get("dataset_id") or "").strip() or None,
        "dataset_sha256": dataset_sha,
        "content_sha256": str(manifest.get("content_sha256") or "").strip(),
        "checks": checks,
        "failures": unique_failures,
    }


def certify_dataset_snapshot(manifest: dict, snapshot: dict) -> dict:
    """Certify the actual immutable OHLCV bundle, not merely its description."""
    result = certify_dataset_manifest(manifest)
    failures = list(result.get("failures") or [])
    checks = dict(result.get("checks") or {})
    series = snapshot.get("series") if isinstance(snapshot, dict) else None
    if not isinstance(series, list) or not series:
        failures.append("snapshot_series_missing")
        series = []

    try:
        actual_hash = hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()
    except (TypeError, ValueError):
        actual_hash = ""
        failures.append("snapshot_not_canonicalizable")
    hash_matches = bool(actual_hash and actual_hash == result.get("content_sha256"))
    checks["snapshot_content_hash_matches"] = hash_matches
    if not hash_matches:
        failures.append("snapshot_content_hash_mismatch")

    identities: set[tuple[str, str]] = set()
    observed_timestamps: list[datetime] = []
    snapshot_valid = bool(series)
    for item in series:
        if not isinstance(item, dict):
            snapshot_valid = False
            continue
        symbol = str(item.get("symbol") or "").strip()
        bar = str(item.get("bar") or "").strip()
        identity = (symbol, bar.upper())
        rows = item.get("rows")
        if not symbol or not bar or identity in identities or not isinstance(rows, list) or not rows:
            snapshot_valid = False
            continue
        identities.add(identity)
        previous = None
        for row in rows:
            if not isinstance(row, dict):
                snapshot_valid = False
                continue
            try:
                ts = int(row["ts"])
                open_px = float(row["open"])
                high_px = float(row["high"])
                low_px = float(row["low"])
                close_px = float(row["close"])
                volume = float(row["volume"])
            except (KeyError, TypeError, ValueError):
                snapshot_valid = False
                continue
            values = (open_px, high_px, low_px, close_px, volume)
            if (
                ts <= 0
                or previous is not None and ts <= previous
                or not all(isfinite(value) for value in values)
                or min(open_px, high_px, low_px, close_px) <= 0
                or high_px < max(open_px, low_px, close_px)
                or low_px > min(open_px, high_px, close_px)
                or volume < 0
            ):
                snapshot_valid = False
                continue
            previous = ts
            observed_timestamps.append(datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc))

    checks["snapshot_market_data_valid"] = snapshot_valid
    if not snapshot_valid:
        failures.append("snapshot_market_data_invalid")

    start = _parse_timestamp(manifest.get("start_timestamp"))
    end = _parse_timestamp(manifest.get("end_timestamp"))
    range_matches = bool(
        observed_timestamps
        and start is not None
        and end is not None
        and start == min(observed_timestamps)
        and end == max(observed_timestamps)
    )
    checks["snapshot_timestamp_range_matches"] = range_matches
    if not range_matches:
        failures.append("snapshot_timestamp_range_mismatch")

    unique_failures = list(dict.fromkeys(failures))
    return {
        **result,
        "certified": not unique_failures,
        "snapshot_verified": not unique_failures,
        "snapshot_content_sha256": actual_hash,
        "checks": checks,
        "failures": unique_failures,
    }

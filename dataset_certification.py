"""Fail-closed certification for deterministic research dataset manifests."""

from __future__ import annotations

from datetime import datetime
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
        "checks": checks,
        "failures": unique_failures,
    }

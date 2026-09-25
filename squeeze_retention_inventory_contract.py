"""Fail-closed inventory audit for the squeeze-retention data contract.

The audit is deliberately outcome-free.  It verifies only whether a complete
historical object inventory could support later pre-outcome research.  Missing
liquidation objects are never interpreted as zero liquidation notional.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re


UTC = timezone.utc
FROZEN_START = datetime(2025, 7, 1, tzinfo=UTC)
FROZEN_END = datetime(2026, 9, 1, tzinfo=UTC)
FROZEN_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DENSE_FAMILIES = ("open_interest", "mark_price")
FAMILIES = ("liquidations", *DENSE_FAMILIES)
LEGACY_SUFFIX_CUTOFF = datetime(2026, 8, 19, tzinfo=UTC)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PATH_RE = re.compile(
    r"^binance_futures/(?P<date>\d{4}-\d{2}-\d{2})/(?P<hour>\d{2})/"
    r"(?P<symbol>[A-Z0-9]+)_(?P<family>liquidations|open_interest|mark_price)"
    r"(?P<suffix>\.parquet(?:\.zst)?)$"
)


def _hours(start: datetime, end: datetime):
    hour = start
    while hour < end:
        yield hour
        hour += timedelta(hours=1)


def _normalize_hour(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name}_must_be_utc")
    if value.minute or value.second or value.microsecond:
        raise ValueError(f"{name}_must_be_hour_aligned")
    return value.astimezone(UTC)


def _parse_entry(entry, start, end, symbols):
    if not isinstance(entry, dict):
        raise ValueError("entry_not_object")
    match = PATH_RE.fullmatch(entry.get("object_path", ""))
    if not match:
        raise ValueError("object_path_invalid")
    hour = datetime.fromisoformat(
        f"{match.group('date')}T{match.group('hour')}:00:00+00:00"
    )
    symbol = match.group("symbol")
    family = match.group("family")
    if not start <= hour < end or symbol not in symbols:
        raise ValueError("object_outside_frozen_cohort")
    required_suffix = ".parquet.zst" if hour < LEGACY_SUFFIX_CUTOFF else ".parquet"
    if match.group("suffix") != required_suffix:
        raise ValueError("object_suffix_mismatch")
    size = entry.get("size_bytes")
    if type(size) is not int or size <= 0:
        raise ValueError("object_size_invalid")
    digest = entry.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest.lower()):
        # An S3 ETag is intentionally not accepted as an immutable SHA-256.
        raise ValueError("sha256_required")
    return hour, symbol, family


def audit_inventory(
    entries,
    *,
    start=FROZEN_START,
    end=FROZEN_END,
    symbols=FROZEN_SYMBOLS,
    listing_complete: bool,
    receipt_semantics_verified: bool,
    contract_units_verified: bool,
):
    """Audit one exact-prefix listing without touching prices or returns.

    The three capability flags are structural assertions supplied by the
    caller.  They can expose whether this inventory is internally ready for a
    later authority check, but they cannot themselves authorize feature use.
    Authorization requires a separately trusted, durable source-resolution
    receipt that proves the provider listing, receipt semantics, and contract
    units without relying on the caller's assertions.
    """
    start = _normalize_hour(start, "start")
    end = _normalize_hour(end, "end")
    if end <= start:
        raise ValueError("end_must_follow_start")
    symbols = tuple(symbols)
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate_symbols")

    parsed = []
    invalid = Counter()
    for entry in entries:
        try:
            parsed.append(_parse_entry(entry, start, end, symbols))
        except ValueError as exc:
            invalid[str(exc)] += 1

    identity_counts = Counter(parsed)
    duplicates = sum(count - 1 for count in identity_counts.values() if count > 1)
    valid_keys = {key for key, count in identity_counts.items() if count == 1}

    hours = list(_hours(start, end))
    dense_expected = len(hours) * len(symbols) * len(DENSE_FAMILIES)
    dense_keys = {
        (hour, symbol, family)
        for hour in hours
        for symbol in symbols
        for family in DENSE_FAMILIES
    }
    dense_verified = len(dense_keys & valid_keys)

    no_publication = 0
    collection_unknown = 0
    liquidation_files = 0
    for hour in hours:
        for symbol in symbols:
            liquidation = (hour, symbol, "liquidations")
            if liquidation in valid_keys:
                liquidation_files += 1
                continue
            dense_healthy = all(
                (hour, symbol, family) in valid_keys for family in DENSE_FAMILIES
            )
            # Provider-declared sparse-file semantics can only be applied to an
            # exhaustive listing and an hour with independent collector health.
            if listing_complete and dense_healthy:
                no_publication += 1
            else:
                collection_unknown += 1

    blockers = []
    if not listing_complete:
        blockers.append("complete_prefix_inventory_unavailable")
    if invalid or duplicates:
        blockers.append("inventory_integrity_failed")
    if dense_verified != dense_expected:
        blockers.append("dense_coverage_incomplete")
    if collection_unknown:
        blockers.append("liquidation_absence_ambiguous")
    if not receipt_semantics_verified:
        blockers.append("historical_receipt_semantics_unverified")
    if not contract_units_verified:
        blockers.append("contract_and_notional_units_unverified")

    structure_ready = not blockers
    if structure_ready:
        blockers.append("trusted_source_authority_required")

    return {
        "schema_version": 1,
        "status": (
            "WAIT_TRUSTED_SOURCE_AUTHORITY"
            if structure_ready
            else "TERMINAL_DATA_BLOCKER"
        ),
        "frozen_interval": {
            "start_inclusive": start.isoformat().replace("+00:00", "Z"),
            "end_exclusive": end.isoformat().replace("+00:00", "Z"),
        },
        "symbols": list(symbols),
        "families": list(FAMILIES),
        "listing_complete": bool(listing_complete),
        "caller_asserted_capabilities": {
            "listing_complete": bool(listing_complete),
            "receipt_semantics_verified": bool(receipt_semantics_verified),
            "contract_units_verified": bool(contract_units_verified),
        },
        "structure_ready": structure_ready,
        "authorization_scope": "STRUCTURE_ONLY",
        "valid_objects": len(valid_keys),
        "invalid_objects": sum(invalid.values()),
        "invalid_reasons": dict(sorted(invalid.items())),
        "duplicate_objects": duplicates,
        "dense_expected": dense_expected,
        "dense_verified": dense_verified,
        "liquidation_files_verified": liquidation_files,
        "no_published_liquidation_file_hours": no_publication,
        "collection_unknown_liquidation_hours": collection_unknown,
        "missing_liquidation_means_zero_notional": False,
        "liquidation_volume_semantics": "LOWER_BOUND_PUBLIC_BROADCAST_ONLY",
        "decision_time_field": "received_time",
        "event_time_used_as_availability": False,
        "estimated_hour_plus_15m_used_as_availability": False,
        "outcomes_inspected": False,
        "untouched_oos_opened": False,
        "feature_authorized": False,
        "blockers": blockers,
    }

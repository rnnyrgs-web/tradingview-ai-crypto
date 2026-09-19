"""Outcome-free replay of the fixed CryptoHFTData feasibility sample.

This module cannot certify a research contract. It never calculates returns.
Only the optional Parquet reader needs pyarrow; pure audit tests use no extras.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

HOUR_NS = 3_600_000_000_000
START_NS = 1788350400000000000  # 2026-09-02T12:00:00Z
MAX_BYTES = 8 * 1024 * 1024
BASE_URL = "https://api.cryptohftdata.com/v1/download?file="
FIELDS = {
    "liquidations": ("event_time", "trade_time", "side", "quantity", "price",
                     "average_price", "filled_quantity"),
    "open_interest": ("timestamp", "sum_open_interest", "sum_open_interest_value"),
    "mark_price": ("event_time", "mark_price", "index_price", "funding_rate",
                   "next_funding_time"),
}
NUMERIC = {
    "liquidations": ("quantity", "price", "average_price", "filled_quantity"),
    "open_interest": ("sum_open_interest", "sum_open_interest_value"),
    "mark_price": ("mark_price", "index_price", "funding_rate"),
}


def sample_objects():
    """Fixed cohort/hour selected before outcomes; no replacement search."""
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for family in FIELDS:
            name = f"{symbol}_{family}.parquet"
            path = f"binance_futures/2026-09-02/12/{name}"
            yield dict(symbol=symbol, family=family, file=name,
                       object_path=path, url=BASE_URL + path)


def _timestamp(value, scale):
    if type(value) is not int:
        raise ValueError("timestamp_type")
    ns = value * scale
    # Explicit units, no auto-detection or silent coercion (including booleans).
    if not 946684800000000000 <= ns < 4102444800000000000:
        raise ValueError("timestamp_unit_or_range")
    return ns


def available_asof(rows, decision_ns, publication_ns):
    """Reference as-of guard, only with externally proved object publication.

    Acquisition today or an estimated hour+15m delay is NOT such proof. This
    helper is tested synthetically; no sample has verified publication time.
    """
    if publication_ns is None:
        raise ValueError("archive publication proof required")
    publication_ns = _timestamp(publication_ns, 1)
    decision_ns = _timestamp(decision_ns, 1)
    receipts = [_timestamp(row["received_time"], 1) for row in rows]
    if any(receipt > publication_ns for receipt in receipts):
        raise ValueError("publication before collector receipt")
    return list(rows) if publication_ns <= decision_ns else []


def audit_rows(rows, symbol, family):
    """Check documented Binance timestamp units; summarize, never repair rows."""
    required = {"symbol", "received_time", *FIELDS[family]}
    errors = Counter()
    receipts, events, ages, fingerprints = [], [], [], []
    if not rows:
        errors["empty_file"] += 1
    for row in rows:
        if not isinstance(row, dict) or not required <= row.keys():
            errors["missing_fields"] += 1
            continue
        fingerprints.append(json.dumps(row, sort_keys=True, allow_nan=False))
        if row["symbol"] != symbol:
            errors["wrong_symbol"] += 1
        try:
            receipt = _timestamp(row["received_time"], 1)
            event = _timestamp(row["timestamp" if family == "open_interest" else "event_time"], 1_000_000)
            receipts.append(receipt)
            events.append(event)
            ages.append((receipt - event) / 1_000_000)
            if not START_NS <= receipt < START_NS + HOUR_NS:
                errors["receipt_outside_hour"] += 1
            if event > receipt:
                errors["event_after_receipt"] += 1
            if family == "liquidations" and _timestamp(row["trade_time"], 1_000_000) > event:
                errors["trade_after_event"] += 1
            if family == "mark_price" and _timestamp(row["next_funding_time"], 1_000_000) < event:
                errors["funding_time_before_event"] += 1
        except ValueError as exc:
            errors[str(exc)] += 1
        if family == "liquidations" and row["side"] not in ("BUY", "SELL"):
            errors["invalid_side"] += 1
        for field in NUMERIC[family]:
            try:
                value = row[field]
                if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                    raise ValueError
                number = Decimal(str(value))
                if not number.is_finite() or (field != "funding_rate" and number <= 0):
                    raise ValueError
            except (ValueError, InvalidOperation):
                errors["invalid_numeric"] += 1
    unique_events = sorted(set(events))
    gaps = [(b - a) // 1_000_000 for a, b in zip(unique_events, unique_events[1:])]
    return {
        "row_count": len(rows), "errors": dict(sorted(errors.items())),
        "feature_authorized": False,
        "duplicate_rows": len(fingerprints) - len(set(fingerprints)),
        "unique_event_timestamps": len(unique_events),
        "repeated_event_timestamps": len(events) - len(unique_events),
        "receipt_order_inversions": sum(b < a for a, b in zip(receipts, receipts[1:])),
        "event_order_inversions": sum(b < a for a, b in zip(events, events[1:])),
        "events_before_receipt_hour": sum(event < START_NS for event in events),
        "receipt_ns_min": min(receipts, default=None), "receipt_ns_max": max(receipts, default=None),
        "event_ns_min": min(events, default=None), "event_ns_max": max(events, default=None),
        "event_age_ms_min": min(ages, default=None), "event_age_ms_max": max(ages, default=None),
        "unique_event_gap_ms_min": min(gaps, default=None),
        "unique_event_gap_ms_max": max(gaps, default=None),
    }


def read_parquet(path):
    import pyarrow.parquet as pq  # Optional offline research dependency.

    file = pq.ParquetFile(path)
    if file.metadata.num_rows > 100_000:
        raise ValueError("row_budget_exceeded")
    return file.read().to_pylist()


def audit_cache(root, reader=read_parquet):
    """Offline, hash-checked replay. Never trusts manifest paths or sources."""
    root = Path(root)
    entries = json.loads((root / "manifest.json").read_text())
    objects, failures = [], []
    expected = list(sample_objects())
    identities = [(entry.get("symbol"), entry.get("family")) for entry in entries]
    if len(entries) != 9 or set(identities) != {(s["symbol"], s["family"]) for s in expected}:
        failures.append("manifest_cohort_mismatch")
    for spec in expected:
        item = dict(spec)
        matches = [entry for entry in entries if (entry.get("symbol"), entry.get("family")) ==
                   (spec["symbol"], spec["family"])]
        try:
            if len(matches) != 1:
                raise ValueError("missing_or_duplicate_manifest_entry")
            entry = matches[0]
            if any(entry.get(key) != value for key, value in spec.items()):
                raise ValueError("manifest_source_or_path_mismatch")
            if entry.get("status") != "downloaded" or entry.get("http_status") != 200:
                raise ValueError("object_unavailable_not_zero_events")
            acquired = datetime.fromisoformat(entry["acquired_at"])
            if acquired.tzinfo is None or acquired.utcoffset().total_seconds() != 0:
                raise ValueError("acquisition_must_be_utc")
            if acquired < datetime(2026, 9, 2, 13, tzinfo=timezone.utc):
                raise ValueError("acquisition_before_hour_closed")
            path = root / spec["file"]
            if path.is_symlink():
                raise ValueError("symlink_not_allowed")
            if not 0 < path.stat().st_size <= MAX_BYTES:
                raise ValueError("object_byte_budget_exceeded")
            data = path.read_bytes()
            if len(data) != entry.get("size_bytes") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise ValueError("object_hash_or_size_mismatch")
            item.update(sha256=entry["sha256"], size_bytes=len(data), acquired_at=entry["acquired_at"])
            item["audit"] = audit_rows(reader(path), spec["symbol"], spec["family"])
            if item["audit"]["errors"]:
                raise ValueError("row_structure_failed")
            item["status"] = "sample_structure_verified"
        except (ValueError, TypeError, KeyError, OSError) as exc:
            item.update(status="failed", error=str(exc))
            failures.append(spec["file"])
        objects.append(item)
    blockers = ["historical_coverage_unproved", "archive_publication_unproved",
                "missing_hour_semantics_unproved", "contract_units_not_independently_verified",
                "sampled_liquidation_feed_not_complete_market_notional"]
    if failures:
        blockers.append("sample_integrity_or_structure_failed")
    return dict(schema_version=1, status="INSUFFICIENT_FOR_FROZEN_SCREEN",
                feature_authorized=False, outcomes_inspected=False,
                sample_hour="2026-09-02T12:00:00Z", verified_objects=sum(
                    item["status"] == "sample_structure_verified" for item in objects),
                blockers=blockers, failures=failures, objects=objects)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_cache(args.cache)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    # 0 means the sample replay passed, never that research is authorized.
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

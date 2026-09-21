"""Outcome-blind qualification for Strategy Factory Cohort-001 source data.

This module deliberately stops at dataset identity, provenance, schema, cadence and
chronology.  It never computes returns, signals, labels, P&L or any other economic
outcome.  The goal is to remove a data-readiness blocker without opening the
protected Strategy Factory evidence window.
"""
from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_leadlag_selection import (
    DATASET_PATH,
    FROZEN_DATASET_SHA256,
    _load_contract,
    _validate_histories,
)
from research_artifact import sha256_hex

EXPECTED_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)
EXPECTED_BAR = "1H"
DEVELOPMENT_END_UTC = "2026-08-31T23:00:00+00:00"
PROTECTED_START_UTC = "2026-09-01T00:00:00+00:00"
HOUR_SECONDS = 3600


def _parse_hour(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("chronology boundary must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("chronology boundary must be aligned to the UTC hourly grid")
    return parsed


def _iso_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


def _contains_forbidden_market_values(value: Any) -> bool:
    forbidden = {"open", "high", "low", "close", "volume", "quote_volume", "return", "pnl", "profit_factor"}
    if isinstance(value, dict):
        return any(str(key).lower() in forbidden or _contains_forbidden_market_values(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_market_values(item) for item in value)
    return False


def qualify_cohort001_dataset(
    path: Path = DATASET_PATH,
    *,
    expected_dataset_sha256: str = FROZEN_DATASET_SHA256,
    development_end_utc: str = DEVELOPMENT_END_UTC,
    protected_start_utc: str = PROTECTED_START_UTC,
) -> dict[str, Any]:
    """Return a deterministic metadata-only qualification receipt.

    The full immutable source is validated because its exact identity is already
    part of the certified repository contract.  Only timestamps are used to form
    the Cohort-001 development window.  Protected-period OHLCV values are never
    copied into the receipt or transformed into outcomes.
    """
    development_end = _parse_hour(development_end_utc)
    protected_start = _parse_hour(protected_start_utc)
    if development_end >= protected_start:
        raise ValueError("development window must end strictly before protected evidence")
    if int((protected_start - development_end).total_seconds()) != HOUR_SECONDS:
        raise ValueError("Cohort-001 development/protected boundary must be contiguous hourly chronology")

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        dataset = json.load(handle)

    actual_dataset_sha256 = sha256_hex(dataset)
    if actual_dataset_sha256 != expected_dataset_sha256:
        raise RuntimeError("selection dataset identity mismatch")
    if dataset.get("source") != "OKX /api/v5/market/history-candles":
        raise RuntimeError("unexpected dataset source")
    if dataset.get("bar") != EXPECTED_BAR:
        raise RuntimeError("unexpected dataset bar interval")
    if tuple(dataset.get("fixed_instruments") or ()) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("unexpected fixed instrument set or order")

    contract = _load_contract()
    histories = _validate_histories(dataset["histories"], contract, exact_dataset=True)
    if tuple(contract["source"]["required_instruments"]) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("certified source contract instrument set changed")

    cutoff_ms = int(development_end.timestamp() * 1000)
    protected_ms = int(protected_start.timestamp() * 1000)
    per_instrument: dict[str, dict[str, Any]] = {}
    common_development_timestamps: list[int] | None = None

    for instrument in EXPECTED_INSTRUMENTS:
        rows = histories[instrument]
        source_timestamps = [int(row["ts"]) for row in rows]
        development_timestamps = [ts for ts in source_timestamps if ts <= cutoff_ms]
        protected_timestamps = [ts for ts in source_timestamps if ts >= protected_ms]
        if not development_timestamps:
            raise RuntimeError(f"no development rows for {instrument}")
        if development_timestamps[-1] != cutoff_ms:
            raise RuntimeError(f"development cutoff is not present for {instrument}")
        if any(ts >= protected_ms for ts in development_timestamps):
            raise RuntimeError("protected timestamp leaked into development selection")
        if common_development_timestamps is None:
            common_development_timestamps = development_timestamps
        elif development_timestamps != common_development_timestamps:
            raise RuntimeError("development timestamps are not exactly aligned across instruments")

        per_instrument[instrument] = {
            "source_rows": len(source_timestamps),
            "development_rows": len(development_timestamps),
            "protected_rows_excluded": len(protected_timestamps),
            "source_start_utc": _iso_from_ms(source_timestamps[0]),
            "source_end_utc": _iso_from_ms(source_timestamps[-1]),
            "development_start_utc": _iso_from_ms(development_timestamps[0]),
            "development_end_utc": _iso_from_ms(development_timestamps[-1]),
        }

    common_development_timestamps = common_development_timestamps or []
    timestamp_identity = sha256_hex(
        {
            "bar": EXPECTED_BAR,
            "instruments": list(EXPECTED_INSTRUMENTS),
            "timestamps_ms": common_development_timestamps,
        }
    )
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "qualification_id": "COHORT-001-SELECTION-DATA-PREFLIGHT-v1",
        "status": "QUALIFIED_DEVELOPMENT_ONLY",
        "source_ref": str(path.relative_to(Path(__file__).resolve().parent)) if path.is_relative_to(Path(__file__).resolve().parent) else str(path),
        "source_dataset_sha256": actual_dataset_sha256,
        "source": dataset["source"],
        "bar": EXPECTED_BAR,
        "instruments": list(EXPECTED_INSTRUMENTS),
        "development_end_utc": development_end.isoformat(),
        "protected_start_utc": protected_start.isoformat(),
        "development_timestamp_identity_sha256": timestamp_identity,
        "development_common_timestamps": len(common_development_timestamps),
        "development_rows_total": len(common_development_timestamps) * len(EXPECTED_INSTRUMENTS),
        "protected_rows_excluded_total": sum(item["protected_rows_excluded"] for item in per_instrument.values()),
        "per_instrument": per_instrument,
        "checks": {
            "exact_certified_dataset_identity": True,
            "exact_fixed_instrument_set": True,
            "hourly_grid_monotonic_unique_common": True,
            "finite_nonnegative_volume_and_positive_valid_ohlc": True,
            "development_cutoff_present": True,
            "protected_timestamp_excluded_from_development": True,
        },
        "economic_outcomes_computed": False,
        "strategy_signals_computed": False,
        "protected_market_values_exported": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
    }
    if _contains_forbidden_market_values(receipt):
        raise RuntimeError("qualification receipt attempted to expose market values or outcomes")
    receipt["receipt_sha256"] = sha256_hex(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = qualify_cohort001_dataset(args.dataset)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

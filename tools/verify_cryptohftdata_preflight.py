#!/usr/bin/env python3
"""Deterministic, pre-outcome source verification for COORD-DISC-DATA-003.

This script intentionally does NOT read strategy returns.  It verifies only the
fixed Binance USDⓈ-M BTCUSDT/ETHUSDT/SOLUSDT CryptoHFTData candidate described
in docs/research/squeeze_retention_data_preflight_20260919.md.

The output cannot promote the source directly to strategy evidence.  Even a
clean run reports that full per-symbol historical coverage still needs an exact
coverage enumeration before the frozen squeeze/retention screen may run.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

API_BASE = "https://api.cryptohftdata.com/v1"
EXCHANGE = "binance_futures"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DATA_TYPES = ("liquidations", "open_interest", "mark_price")
EXPECTED_COLUMNS = {
    "liquidations": {
        "received_time",
        "event_time",
        "trade_time",
        "symbol",
        "side",
        "quantity",
        "price",
    },
    "open_interest": {
        "received_time",
        "timestamp",
        "symbol",
        "sum_open_interest",
        "sum_open_interest_value",
    },
    "mark_price": {
        "received_time",
        "event_time",
        "symbol",
        "mark_price",
        "index_price",
        "funding_rate",
        "next_funding_time",
    },
}

# Frozen before any file contents are read.  2026-09-02 is the provider's
# documented public sample date.  2025-06-28 is the documented Binance archive
# start.  2026-09-18 is the last fully closed UTC day at the time this contract
# was written, used only for continuity/data-shape verification.
PROBE_DATES = ("2025-06-28", "2026-09-02", "2026-09-18")
DENSE_HOURS = (0, 12, 23)
LIQUIDATION_FULL_DAY_DATES = ("2026-09-02", "2026-09-18")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def object_path(symbol: str, data_type: str, date: str, hour: int) -> str:
    return f"{EXCHANGE}/{date}/{hour:02d}/{symbol}_{data_type}.parquet"


def infer_timestamp_unit(value: int | float | str | None) -> str | None:
    """Infer Unix epoch scale conservatively from magnitude."""
    if value is None:
        return None
    try:
        magnitude = abs(int(value))
    except (TypeError, ValueError):
        return None
    if magnitude >= 10**17:
        return "ns"
    if magnitude >= 10**14:
        return "us"
    if magnitude >= 10**11:
        return "ms"
    if magnitude >= 10**8:
        return "s"
    return None


def to_ns(value: int | float | str | None, unit: str | None = None) -> int | None:
    if value is None:
        return None
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    unit = unit or infer_timestamp_unit(v)
    factor = {"s": 10**9, "ms": 10**6, "us": 10**3, "ns": 1}.get(unit or "")
    return None if factor is None else v * factor


class RateLimitedClient:
    def __init__(self, min_interval_seconds: float = 1.05, timeout_seconds: float = 30.0):
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def request(self, url: str) -> tuple[int, bytes, dict[str, str]]:
        self._wait()
        req = urllib.request.Request(url, headers={"User-Agent": "tradingview-ai-crypto-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read()
                status = int(response.status)
                headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = int(exc.code)
            headers = {k.lower(): v for k, v in exc.headers.items()}
            if status == 429:
                retry_after = float(headers.get("retry-after", "2") or 2)
                time.sleep(min(max(retry_after, 1.0), 60.0))
        finally:
            self._last_request_at = time.monotonic()
        return status, body, headers

    def get_json(self, path: str, params: dict[str, str]) -> tuple[int, Any, dict[str, str]]:
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
        status, body, headers = self.request(url)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = None
        return status, payload, headers

    def download(self, file_path: str) -> tuple[int, bytes, dict[str, str], str]:
        url = f"{API_BASE}/download?{urllib.parse.urlencode({'file': file_path})}"
        status, body, headers = self.request(url)
        return status, body, headers, url


def read_parquet(data: bytes) -> tuple[list[str], dict[str, list[Any]]]:
    # Lazy import so repository unit tests do not require pyarrow.  The dedicated
    # verification workflow installs pyarrow explicitly.
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore

    table = pq.read_table(pa.BufferReader(data))
    return list(table.column_names), table.to_pydict()


def _nonnull(values: Iterable[Any]) -> list[Any]:
    return [v for v in values if v is not None]


def _duplicate_rows(columns: list[str], data: dict[str, list[Any]]) -> int:
    if not columns:
        return 0
    row_count = len(data[columns[0]])
    seen: set[tuple[str, ...]] = set()
    duplicates = 0
    for idx in range(row_count):
        row = tuple(repr(data[col][idx]) for col in columns)
        if row in seen:
            duplicates += 1
        else:
            seen.add(row)
    return duplicates


def analyze_file(symbol: str, data_type: str, path: str, body: bytes, acquired_at: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "object_path": path,
        "acquired_at": acquired_at,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "symbol_expected": symbol,
        "data_type": data_type,
        "valid": False,
        "errors": [],
    }
    try:
        columns, data = read_parquet(body)
    except Exception as exc:
        result["errors"].append(f"parquet_read_failed:{type(exc).__name__}:{exc}")
        return result

    result["columns"] = columns
    missing = sorted(EXPECTED_COLUMNS[data_type] - set(columns))
    result["missing_expected_columns"] = missing
    if missing:
        result["errors"].append(f"missing_columns:{','.join(missing)}")

    row_count = len(data[columns[0]]) if columns else 0
    result["rows"] = row_count
    result["exact_duplicate_rows"] = _duplicate_rows(columns, data)
    if row_count == 0:
        result["errors"].append("empty_file")

    symbols = sorted({str(v) for v in _nonnull(data.get("symbol", []))})
    result["symbols_observed"] = symbols
    if symbols != [symbol]:
        result["errors"].append(f"symbol_identity_mismatch:{symbols}")

    ts_fields = {
        "liquidations": ("received_time", "event_time", "trade_time"),
        "open_interest": ("received_time", "timestamp"),
        "mark_price": ("received_time", "event_time", "next_funding_time"),
    }[data_type]
    timestamp_units: dict[str, list[str]] = {}
    for field in ts_fields:
        units = sorted({u for u in (infer_timestamp_unit(v) for v in _nonnull(data.get(field, []))) if u})
        timestamp_units[field] = units
        if field != "next_funding_time" and len(units) != 1:
            result["errors"].append(f"ambiguous_timestamp_unit:{field}:{units}")
    result["timestamp_units"] = timestamp_units

    if "received_time" in data:
        receive_units = timestamp_units.get("received_time", [])
        if receive_units != ["ns"]:
            result["errors"].append(f"received_time_not_ns:{receive_units}")

    source_field = "event_time" if data_type in {"liquidations", "mark_price"} else "timestamp"
    if source_field in data and "received_time" in data:
        lags_ms: list[float] = []
        for recv, event in zip(data["received_time"], data[source_field]):
            recv_ns = to_ns(recv)
            event_ns = to_ns(event)
            if recv_ns is not None and event_ns is not None:
                lags_ms.append((recv_ns - event_ns) / 1_000_000)
        if lags_ms:
            ordered = sorted(lags_ms)
            result["receive_minus_exchange_ms"] = {
                "count": len(ordered),
                "min": ordered[0],
                "median": statistics.median(ordered),
                "p95": ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))],
                "max": ordered[-1],
                "negative_count": sum(1 for value in ordered if value < 0),
            }

    # Unit semantics are checked structurally without using any strategy return.
    if data_type == "liquidations":
        result["unit_semantics"] = {
            "quantity": "base/contract quantity published by Binance; stored as decimal string",
            "price": "USDT quote price per underlying unit; stored as decimal string",
            "side": "BUY=short liquidation; SELL=long liquidation per provider documentation",
            "forced_flow_use": "proxy/intensity only; public exchange feed may be sampled",
        }
    elif data_type == "open_interest":
        result["unit_semantics"] = {
            "sum_open_interest": "contracts/base contract quantity as published by exchange",
            "sum_open_interest_value": "quote-notional value when exchange supplies it",
        }
    else:
        result["unit_semantics"] = {
            "mark_price": "USDT quote price",
            "index_price": "USDT quote price",
            "funding_rate": "dimensionless rate for perpetual contract",
            "next_funding_time": "exchange funding timestamp",
        }

    result["valid"] = not result["errors"]
    return result


def build_probe_paths() -> list[tuple[str, str, str, int, str]]:
    probes: list[tuple[str, str, str, int, str]] = []
    for symbol in SYMBOLS:
        # Dense feeds: fixed start/sample/recent hours.
        for data_type in ("open_interest", "mark_price"):
            for date in PROBE_DATES:
                for hour in DENSE_HOURS:
                    probes.append((symbol, data_type, date, hour, object_path(symbol, data_type, date, hour)))
        # Sparse feed: full-day enumeration on provider sample date + recent day.
        for date in LIQUIDATION_FULL_DAY_DATES:
            for hour in range(24):
                probes.append((symbol, "liquidations", date, hour, object_path(symbol, "liquidations", date, hour)))
        # Also probe the documented archive-start date at three fixed hours.
        for hour in DENSE_HOURS:
            probes.append((symbol, "liquidations", PROBE_DATES[0], hour, object_path(symbol, "liquidations", PROBE_DATES[0], hour)))
    return probes


def verify(output_json: Path, output_md: Path, min_interval: float) -> dict[str, Any]:
    client = RateLimitedClient(min_interval_seconds=min_interval)
    report: dict[str, Any] = {
        "task_id": "COORD-DISC-DATA-003",
        "candidate": "DISC-SQUEEZE-RETENTION-001-v1",
        "source": "CryptoHFTData",
        "venue": EXCHANGE,
        "symbols": list(SYMBOLS),
        "data_types": list(DATA_TYPES),
        "started_at": utc_now(),
        "strategy_outcomes_accessed": False,
        "oos_accessed": False,
        "sampled_public_liquidation_feed_is_lower_bound": True,
        "missing_liquidation_file_semantics": "provider documents that hourly files exist only when at least one liquidation event was published for the symbol; absence is zero PUBLISHED events, not proof of zero actual forced liquidation volume",
        "availability_clock_rule": "feature values may be used only at decision timestamps >= received_time; exchange event timestamps are descriptive, not the availability clock",
        "symbols_api": {},
        "probes": [],
        "failures": [],
    }

    for data_type in DATA_TYPES:
        status, payload, headers = client.get_json("/symbols", {"exchange": EXCHANGE, "data_type": data_type})
        entry = {
            "http_status": status,
            "rate_limit": {k: headers.get(k) for k in ("ratelimit", "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset") if headers.get(k)},
            "count": payload.get("count") if isinstance(payload, dict) else None,
            "required_symbols_present": False,
        }
        if status == 200 and isinstance(payload, dict):
            symbols = set(payload.get("symbols") or [])
            entry["required_symbols_present"] = all(symbol in symbols for symbol in SYMBOLS)
            entry["required_symbols"] = {symbol: symbol in symbols for symbol in SYMBOLS}
        if not entry["required_symbols_present"]:
            report["failures"].append(f"symbols_api_missing_required:{data_type}")
        report["symbols_api"][data_type] = entry

    found_by_symbol_type: dict[str, int] = {f"{s}:{d}": 0 for s in SYMBOLS for d in DATA_TYPES}
    valid_by_symbol_type: dict[str, int] = {f"{s}:{d}": 0 for s in SYMBOLS for d in DATA_TYPES}

    for symbol, data_type, date, hour, path in build_probe_paths():
        acquired_at = utc_now()
        status, body, headers, url = client.download(path)
        probe: dict[str, Any] = {
            "symbol": symbol,
            "data_type": data_type,
            "date": date,
            "hour": hour,
            "object_path": path,
            "request_url": url,
            "http_status": status,
            "acquired_at": acquired_at,
            "rate_limit_remaining": headers.get("ratelimit-remaining"),
        }
        if status == 200:
            key = f"{symbol}:{data_type}"
            found_by_symbol_type[key] += 1
            analysis = analyze_file(symbol, data_type, path, body, acquired_at)
            probe["file"] = analysis
            if analysis["valid"]:
                valid_by_symbol_type[key] += 1
            else:
                report["failures"].append(f"invalid_file:{path}:{analysis['errors']}")
        elif status in (404, 410):
            probe["missing"] = True
            if data_type != "liquidations" and date == "2026-09-02":
                report["failures"].append(f"dense_sample_missing:{path}")
        else:
            # Preserve body only as bounded textual error metadata, never as secret-bearing raw bytes.
            probe["error_body"] = body[:500].decode("utf-8", errors="replace")
            report["failures"].append(f"http_error:{status}:{path}")
        report["probes"].append(probe)

    report["sample_files_found"] = found_by_symbol_type
    report["sample_files_valid"] = valid_by_symbol_type
    for key in sorted(found_by_symbol_type):
        if found_by_symbol_type[key] == 0:
            report["failures"].append(f"no_sample_file_found:{key}")
        elif valid_by_symbol_type[key] == 0:
            report["failures"].append(f"no_valid_sample_file:{key}")

    # This bounded pass deliberately cannot claim exact all-hour historical
    # coverage.  Promotion to a frozen strategy data contract requires an exact
    # prefix/file enumeration (preferred) or an equivalently complete gap audit.
    report["full_historical_coverage_enumerated"] = False
    report["coverage_blocker"] = (
        "Anonymous REST exposes exact hourly objects and symbols but no public prefix/file listing endpoint was identified. "
        "Exact all-hour coverage/gap enumeration remains required before the strategy screen; use read-only flat-file/S3 listing credentials or an equivalently complete bounded enumeration."
    )
    report["technical_sample_status"] = "PASS" if not report["failures"] else "FAIL"
    report["scientific_data_contract_status"] = (
        "NEEDS_EXACT_COVERAGE_ENUMERATION" if not report["failures"] else "INSUFFICIENT_FOR_FROZEN_SCREEN"
    )
    report["finished_at"] = utc_now()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# CryptoHFTData deterministic preflight — COORD-DISC-DATA-003",
        "",
        f"- Technical sample status: **{report['technical_sample_status']}**",
        f"- Scientific data-contract status: **{report['scientific_data_contract_status']}**",
        f"- Venue: `{EXCHANGE}`",
        f"- Fixed symbols: {', '.join(SYMBOLS)}",
        "- Strategy outcomes accessed: **NO**",
        "- Untouched OOS accessed: **NO**",
        "- Liquidation interpretation: sampled public-feed proxy/lower bound only",
        "- Availability rule: use collector `received_time` for chronology",
        "",
        "## Sample file counts",
        "",
    ]
    for key in sorted(found_by_symbol_type):
        lines.append(f"- `{key}`: found {found_by_symbol_type[key]}, valid {valid_by_symbol_type[key]}")
    lines.extend([
        "",
        "## Exact remaining blocker",
        "",
        report["coverage_blocker"],
        "",
        "No strategy threshold, return, benchmark, train/validation outcome, or untouched OOS observation was read by this verifier.",
    ])
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in report["failures"])
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="artifacts/research/cryptohftdata_preflight_report.json")
    parser.add_argument("--output-md", default="artifacts/research/cryptohftdata_preflight_report.md")
    parser.add_argument(
        "--min-interval",
        type=float,
        default=float(os.getenv("CRYPTOHFTDATA_MIN_INTERVAL_SECONDS", "1.05")),
        help="Minimum seconds between anonymous API requests; default stays below documented 60/minute ceiling.",
    )
    args = parser.parse_args()
    report = verify(Path(args.output_json), Path(args.output_md), args.min_interval)
    print(json.dumps({
        "technical_sample_status": report["technical_sample_status"],
        "scientific_data_contract_status": report["scientific_data_contract_status"],
        "failure_count": len(report["failures"]),
        "output_json": args.output_json,
        "output_md": args.output_md,
    }, sort_keys=True))
    # Fail closed only on technical/sample defects.  NEEDS_EXACT_COVERAGE_ENUMERATION
    # is expected and should still publish the evidence artifact for Lead review.
    return 1 if report["technical_sample_status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Point-in-time universe validation for historical research.

A current exchange universe is not proof of historical investability. Listing /
delisting dates alone are also insufficient for cross-sectional Top-N research:
the strategy needs the actual investable/liquid universe that was knowable at
each historical interval. This module therefore requires timestamped universe
snapshots with provenance before cross-sectional research may be called
survivorship-safe. Missing evidence fails closed and is never inferred.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("nonfinite timestamp")
        raw = float(value)
        return datetime.fromtimestamp(raw / 1000.0 if raw > 10_000_000_000 else raw, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _invalid(available, reason, provenance=None):
    return {
        "available": available,
        "valid": False,
        "reason": reason,
        "snapshots": [],
        "provenance": provenance,
    }


def load_manifest(path: str | None) -> dict:
    """Load pre-recorded point-in-time investable-universe intervals.

    Expected JSON:
    {
      "provenance": {"source": "...", "captured_at": "..."},
      "snapshots": [
        {"effective_from":"...", "effective_to":"...", "symbols":["BTC-USDT", ...]}
      ]
    }
    Intervals must be non-overlapping and ordered. `effective_to` may be null only
    for the final interval. No current universe is substituted for missing history.
    """
    if not path:
        return _invalid(False, "point_in_time_snapshot_manifest_not_configured")
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _invalid(True, "point_in_time_snapshot_manifest_unreadable")
    if not isinstance(raw, dict) or not isinstance(raw.get("snapshots"), list):
        return _invalid(True, "point_in_time_snapshot_manifest_malformed")
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("source") or "").strip() or not str(provenance.get("captured_at") or "").strip():
        return _invalid(True, "point_in_time_snapshot_manifest_missing_provenance", provenance)

    snapshots = []
    try:
        _parse_ts(provenance["captured_at"])
        for item in raw["snapshots"]:
            if not isinstance(item, dict) or not isinstance(item.get("symbols"), list):
                raise ValueError("snapshot malformed")
            start = _parse_ts(item.get("effective_from"))
            end = _parse_ts(item.get("effective_to"))
            symbols = sorted({str(s or "").upper().strip() for s in item["symbols"] if str(s or "").strip()})
            if start is None or not symbols or (end is not None and end <= start):
                raise ValueError("snapshot chronology invalid")
            snapshots.append({"effective_from": start, "effective_to": end, "symbols": frozenset(symbols)})
        snapshots.sort(key=lambda row: row["effective_from"])
        if not snapshots:
            raise ValueError("empty snapshot manifest")
        for index, row in enumerate(snapshots):
            if index < len(snapshots) - 1:
                if row["effective_to"] is None or row["effective_to"] > snapshots[index + 1]["effective_from"]:
                    raise ValueError("overlapping/open snapshot intervals")
            elif row["effective_to"] is not None and row["effective_to"] <= row["effective_from"]:
                raise ValueError("invalid final interval")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _invalid(True, "point_in_time_snapshot_manifest_invalid", provenance)

    return {
        "available": True,
        "valid": True,
        "reason": "ok",
        "snapshots": snapshots,
        "provenance": provenance,
    }


def _snapshot_at(manifest: dict, timestamp):
    if not manifest.get("valid"):
        return None
    try:
        ts = _parse_ts(timestamp)
    except (TypeError, ValueError, OverflowError):
        return None
    if ts is None:
        return None
    for snapshot in manifest.get("snapshots") or []:
        if ts < snapshot["effective_from"]:
            break
        end = snapshot["effective_to"]
        if ts >= snapshot["effective_from"] and (end is None or ts < end):
            return snapshot
    return None


def membership_at(manifest: dict, symbol: str, timestamp) -> bool:
    snapshot = _snapshot_at(manifest, timestamp)
    return bool(snapshot and str(symbol or "").upper() in snapshot["symbols"])


def filter_histories(manifest: dict, histories: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict]:
    """Filter actual candles to the point-in-time investable universe.

    Every original candle timestamp must be covered by a manifest interval before
    the result can be promotion-grade. Candles for symbols outside the universe at
    a covered timestamp are deliberately excluded. This does not fabricate missing
    delisted assets or missing candles.
    """
    if not manifest.get("valid"):
        return dict(histories or {}), {
            "survivorship_safe": False,
            "promotion_allowed": False,
            "reason": manifest.get("reason") or "point_in_time_snapshot_manifest_invalid",
            "covered_observations": 0,
            "excluded_nonmember_observations": 0,
            "uncovered_observations": sum(len(rows or []) for rows in (histories or {}).values()),
            "restrictive_only": True,
            "can_authorize_by_itself": False,
        }

    filtered = {}
    covered = excluded = uncovered = malformed = 0
    observed_timestamps = set()
    manifest_member_symbols = set()
    for snapshot in manifest["snapshots"]:
        manifest_member_symbols.update(snapshot["symbols"])

    for symbol, rows in (histories or {}).items():
        kept = []
        for row in rows or []:
            if not isinstance(row, dict) or row.get("ts") is None:
                malformed += 1
                continue
            snapshot = _snapshot_at(manifest, row["ts"])
            if snapshot is None:
                uncovered += 1
                continue
            covered += 1
            try:
                ts = _parse_ts(row["ts"])
            except (TypeError, ValueError, OverflowError):
                malformed += 1
                continue
            observed_timestamps.add(ts)
            if str(symbol).upper() in snapshot["symbols"]:
                kept.append(row)
            else:
                excluded += 1
        if kept:
            filtered[symbol] = kept

    # A manifest may identify historical members that today's survivor-based fetch
    # never attempted. Their absence is exactly the survivorship problem; do not
    # silently declare the universe safe in that case.
    fetched_symbols = {str(symbol).upper() for symbol in (histories or {})}
    missing_manifest_members = sorted(manifest_member_symbols - fetched_symbols)
    safe = bool(filtered) and uncovered == 0 and malformed == 0 and not missing_manifest_members
    reason = "point_in_time_universe_verified" if safe else "point_in_time_universe_incomplete_or_history_mismatch"
    return filtered if safe else dict(histories or {}), {
        "survivorship_safe": safe,
        "promotion_allowed": safe,
        "reason": reason,
        "covered_observations": covered,
        "excluded_nonmember_observations": excluded,
        "uncovered_observations": uncovered,
        "malformed_history_observations": malformed,
        "missing_historical_member_symbols": missing_manifest_members,
        "manifest_snapshot_count": len(manifest["snapshots"]),
        "provenance": manifest.get("provenance"),
        "restrictive_only": True,
        "can_authorize_by_itself": False,
    }


def assess_history_coverage(manifest: dict, histories: dict[str, list[dict]]) -> dict:
    """Backward-compatible assessment helper without mutating the caller's data."""
    _, assessment = filter_histories(manifest, histories)
    return assessment

"""Point-in-time universe validation for historical research.

A current exchange universe is not proof of historical membership. This module
never invents listings or delistings. Promotion-grade survivorship safety
requires an explicit timestamped membership manifest with provenance.
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
        return datetime.fromtimestamp(float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value), tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_manifest(path: str | None) -> dict:
    if not path:
        return {
            "available": False,
            "valid": False,
            "reason": "point_in_time_manifest_not_configured",
            "memberships": {},
            "provenance": None,
        }
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {"available": True, "valid": False, "reason": "point_in_time_manifest_unreadable", "memberships": {}, "provenance": None}
    if not isinstance(raw, dict) or not isinstance(raw.get("memberships"), list):
        return {"available": True, "valid": False, "reason": "point_in_time_manifest_malformed", "memberships": {}, "provenance": None}
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("source") or "").strip() or not str(provenance.get("captured_at") or "").strip():
        return {"available": True, "valid": False, "reason": "point_in_time_manifest_missing_provenance", "memberships": {}, "provenance": provenance}

    memberships = {}
    try:
        _parse_ts(provenance["captured_at"])
        for item in raw["memberships"]:
            if not isinstance(item, dict):
                raise ValueError("membership row malformed")
            symbol = str(item.get("symbol") or "").upper().strip()
            listed = _parse_ts(item.get("listed_at"))
            delisted = _parse_ts(item.get("delisted_at"))
            if not symbol or listed is None or (delisted is not None and delisted <= listed):
                raise ValueError("membership chronology invalid")
            if symbol in memberships:
                raise ValueError("duplicate symbol membership")
            memberships[symbol] = {"listed_at": listed, "delisted_at": delisted}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"available": True, "valid": False, "reason": "point_in_time_manifest_invalid_membership", "memberships": {}, "provenance": provenance}
    if not memberships:
        return {"available": True, "valid": False, "reason": "point_in_time_manifest_empty", "memberships": {}, "provenance": provenance}
    return {"available": True, "valid": True, "reason": "ok", "memberships": memberships, "provenance": provenance}


def membership_at(manifest: dict, symbol: str, timestamp) -> bool:
    if not manifest.get("valid"):
        return False
    item = (manifest.get("memberships") or {}).get(str(symbol or "").upper())
    if not item:
        return False
    try:
        ts = _parse_ts(timestamp)
    except (TypeError, ValueError, OverflowError):
        return False
    if ts is None or ts < item["listed_at"]:
        return False
    return item["delisted_at"] is None or ts < item["delisted_at"]


def assess_history_coverage(manifest: dict, histories: dict[str, list[dict]]) -> dict:
    """Require actual data only while a symbol is declared historically listed.

    This does not fabricate candles for delisted assets. It verifies that supplied
    research histories do not contain observations outside declared membership and
    records whether every researched symbol has membership evidence.
    """
    if not manifest.get("valid"):
        return {
            "survivorship_safe": False,
            "promotion_allowed": False,
            "reason": manifest.get("reason") or "point_in_time_manifest_invalid",
            "missing_membership_symbols": sorted(histories),
            "out_of_membership_observations": 0,
            "restrictive_only": True,
        }
    missing = []
    out_of_window = 0
    malformed = 0
    for symbol, rows in (histories or {}).items():
        if str(symbol).upper() not in manifest["memberships"]:
            missing.append(symbol)
            continue
        for row in rows or []:
            ts = row.get("ts") if isinstance(row, dict) else None
            if ts is None:
                malformed += 1
                continue
            if not membership_at(manifest, symbol, ts):
                out_of_window += 1
    safe = not missing and out_of_window == 0 and malformed == 0 and bool(histories)
    return {
        "survivorship_safe": safe,
        "promotion_allowed": safe,
        "reason": "point_in_time_membership_verified" if safe else "point_in_time_membership_or_history_mismatch",
        "missing_membership_symbols": sorted(missing),
        "out_of_membership_observations": out_of_window,
        "malformed_history_observations": malformed,
        "provenance": manifest.get("provenance"),
        "restrictive_only": True,
        "can_authorize_by_itself": False,
    }

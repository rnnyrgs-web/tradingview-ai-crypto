"""Canonical OHLCV conversion and fingerprinting for cross-engine research."""

from __future__ import annotations

import hashlib
import json
import math
from numbers import Integral


FIELDS = ("ts", "open", "high", "low", "close", "volume")


def canonical_bars(rows):
    out = []
    previous = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed OHLCV row")
        item = {field: row.get(field) for field in FIELDS}
        if isinstance(item["ts"], bool) or not isinstance(item["ts"], Integral):
            raise ValueError("OHLCV timestamp must be an exact integer in nanoseconds")
        try:
            item["ts"] = int(item["ts"])
            for field in FIELDS[1:]:
                item[field] = float(item[field])
        except (TypeError, ValueError, OverflowError):
            raise ValueError("malformed OHLCV row") from None
        if not all(math.isfinite(item[field]) for field in FIELDS[1:]):
            raise ValueError("OHLCV values must be finite")
        if item["ts"] <= 0 or min(item[field] for field in FIELDS[1:5]) <= 0 or item["volume"] < 0:
            raise ValueError("OHLCV requires positive timestamps/prices and nonnegative volume")
        if previous is not None and item["ts"] <= previous:
            raise ValueError("OHLCV timestamps must be strictly increasing")
        if item["high"] < max(item["open"], item["close"], item["low"]) or item["low"] > min(item["open"], item["close"], item["high"]):
            raise ValueError("invalid OHLC price bounds")
        previous = item["ts"]
        out.append(item)
    if len(out) < 2:
        raise ValueError("cross-engine validation requires at least two bars")
    return out


def data_fingerprint(rows) -> str:
    payload = json.dumps(canonical_bars(rows), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verified_bars(contract, bars):
    """Verify the actual execution input against its declared frozen identity."""
    rows = canonical_bars(bars)
    if data_fingerprint(rows) != contract.canonical()["data_fingerprint"]:
        raise ValueError("execution dataset fingerprint disagrees with frozen contract")
    return rows

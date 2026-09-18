"""Canonical OHLCV conversion and fingerprinting for cross-engine research."""

from __future__ import annotations

import hashlib
import json


FIELDS = ("ts", "open", "high", "low", "close", "volume")


def canonical_bars(rows):
    out = []
    previous = None
    for row in rows:
        item = {field: row.get(field) for field in FIELDS}
        try:
            item["ts"] = int(item["ts"])
            for field in FIELDS[1:]:
                item[field] = float(item[field])
        except (TypeError, ValueError):
            raise ValueError("malformed OHLCV row") from None
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
    payload = json.dumps(canonical_bars(rows), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

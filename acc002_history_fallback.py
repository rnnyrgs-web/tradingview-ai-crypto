"""Research-only alternate history acquisition for ACC-002.

This module exists only to recover complete historical price series for an exact
already-ranked asset when the primary OKX history is too short. It never stitches
venues, never substitutes another asset, and never changes the ranked universe.
A fallback series is accepted only when one Bybit spot market alone supplies the
entire requested completed-candle window with strict cadence and positive prices.
"""

from __future__ import annotations

import time

import httpx


BYBIT_V5_BASE = "https://api.bybit.com"
BYBIT_MAX_LIMIT = 1000
SUPPORTED_BARS = {"4H": ("240", 4 * 60 * 60 * 1000)}
MAX_ATTEMPTS = 3

http = httpx.Client(
    timeout=httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0),
    follow_redirects=True,
)


def _bybit_symbol(okx_symbol: str) -> str:
    parts = str(okx_symbol or "").upper().strip().split("-")
    if len(parts) != 2 or parts[1] != "USDT" or not parts[0]:
        raise ValueError("ACC-002 Bybit fallback supports exact BASE-USDT spot symbols only")
    return f"{parts[0]}USDT"


def _get(params: dict) -> list:
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = http.get(f"{BYBIT_V5_BASE}/v5/market/kline", params=params)
            response.raise_for_status()
            payload = response.json()
            if int(payload.get("retCode", -1)) != 0:
                raise RuntimeError("Bybit kline API returned nonzero retCode")
            result = payload.get("result")
            rows = result.get("list") if isinstance(result, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError("Bybit kline API returned malformed list")
            return rows
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
            if attempt + 1 >= MAX_ATTEMPTS:
                raise
            time.sleep(0.35 * (2 ** attempt))
    raise RuntimeError("unreachable Bybit retry state")


def _normalize(rows: list, *, interval_ms: int, now_ms: int) -> list[dict]:
    by_ts = {}
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            continue
        try:
            ts = int(row[0])
            open_ = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            volume = float(row[5])
            quote_volume = float(row[6])
        except (TypeError, ValueError):
            continue
        if ts <= 0 or ts + interval_ms > now_ms:
            continue
        if min(open_, high, low, close) <= 0 or volume < 0 or quote_volume < 0:
            continue
        by_ts[ts] = {
            "ts": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "quote_volume": quote_volume,
        }
    return [by_ts[ts] for ts in sorted(by_ts)]


def _strict_complete_window(rows: list[dict], *, wanted: int, interval_ms: int) -> list[dict]:
    if len(rows) < wanted:
        return []
    rows = rows[-wanted:]
    for left, right in zip(rows, rows[1:]):
        if int(right["ts"]) - int(left["ts"]) != interval_ms:
            return []
    return rows


def get_complete_bybit_spot_history(okx_symbol: str, *, bar: str, bars: int) -> list[dict]:
    """Return one complete Bybit-only series or [] when evidence is insufficient.

    The caller must treat [] as unavailable. No partial series is returned because
    ACC-002 must not stitch venues or manufacture continuity.
    """
    if bar not in SUPPORTED_BARS:
        return []
    wanted = max(1, int(bars))
    interval, interval_ms = SUPPORTED_BARS[bar]
    symbol = _bybit_symbol(okx_symbol)
    now_ms = int(time.time() * 1000)
    end_ms = (now_ms // interval_ms) * interval_ms - 1
    collected = []
    seen_oldest = None

    while len(collected) < wanted:
        limit = min(BYBIT_MAX_LIMIT, wanted - len(collected))
        page = _get({
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "end": str(end_ms),
            "limit": str(limit),
        })
        if not page:
            break
        collected.extend(page)
        try:
            oldest = min(int(row[0]) for row in page if isinstance(row, (list, tuple)) and row)
        except (TypeError, ValueError):
            return []
        if seen_oldest is not None and oldest >= seen_oldest:
            return []
        seen_oldest = oldest
        end_ms = oldest - 1
        if len(page) < limit:
            break
        time.sleep(0.12)

    normalized = _normalize(collected, interval_ms=interval_ms, now_ms=now_ms)
    return _strict_complete_window(normalized, wanted=wanted, interval_ms=interval_ms)

import logging
import math
import time
from datetime import datetime, timezone, timedelta
import httpx

from config import OKX_BASE, MIN_QUOTE_VOLUME, MAX_SPREAD_BPS, STABLE_BASES, UNIVERSE_SIZE
from utils import f, pct_change

log = logging.getLogger(__name__)
http = httpx.Client(timeout=25.0, follow_redirects=True)


_BAR_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1H": 3_600_000, "2H": 7_200_000,
    "4H": 14_400_000, "6H": 21_600_000, "12H": 43_200_000,
    "1D": 86_400_000, "1W": 604_800_000,
}


def okx_get(path, params=None):
    r = http.get(f"{OKX_BASE}{path}", params=params or {})
    r.raise_for_status()
    obj = r.json()
    if str(obj.get("code", "0")) != "0":
        raise RuntimeError(f"OKX error {obj.get('code')}: {obj.get('msg')}")
    return obj.get("data", [])


def get_spot_tickers():
    return okx_get("/api/v5/market/tickers", {"instType": "SPOT"})


def normalize_candles(rows, bar=None):
    """Validate OKX's newest-first candle response, then return oldest-first data.

    Invalid rows are not discarded: silently dropping one can create an
    apparently valid but incomplete backtest window.  Unconfirmed candles are
    the sole intentional omission and are still validated before omission.
    """
    if not isinstance(rows, (list, tuple)):
        raise ValueError("candle response is not a sequence")

    parsed = []
    previous_ts = None
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 9:
            raise ValueError("malformed candle row")
        try:
            ts = int(row[0])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid candle timestamp") from exc
        if previous_ts is not None and ts >= previous_ts:
            raise ValueError("candles are duplicated or not newest-first")
        previous_ts = ts

        values = []
        try:
            values = [float(row[i]) for i in range(1, 6)] + [float(row[7])]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("malformed candle numeric field") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError("non-finite candle value")
        open_, high, low, close, volume, quote_volume = values
        if min(open_, high, low, close) <= 0 or volume < 0 or quote_volume < 0:
            raise ValueError("invalid candle value")
        if high < max(open_, close, low) or low > min(open_, close, high):
            raise ValueError("inconsistent candle OHLC")
        parsed.append((ts, row, open_, high, low, close, volume, quote_volume))

    interval = _BAR_MS.get(bar)
    if interval and len(parsed) > 1:
        timestamps = [item[0] for item in parsed]
        if any(older - newer != interval for newer, older in zip(timestamps, timestamps[1:])):
            raise ValueError("missing or non-contiguous candle")

    out = []
    for ts, row, open_, high, low, close, volume, quote_volume in reversed(parsed):
        if str(row[8]) == "0":
            continue
        out.append({
            "ts": ts, "open": open_, "high": high, "low": low,
            "close": close, "volume": volume, "quote_volume": quote_volume,
        })
    return out


def get_candles(symbol, bar="15m", limit=120):
    rows = okx_get("/api/v5/market/candles", {
        "instId": symbol, "bar": bar, "limit": str(min(limit, 300))
    })
    candles = normalize_candles(rows, bar=bar)
    interval = _BAR_MS.get(bar)
    if candles and interval:
        now_ms = int(time.time() * 1000)
        if now_ms - candles[-1]["ts"] > interval * 3:
            raise ValueError("stale candle response")
    return candles


def get_history(symbol, bar="15m", bars=1000, max_bars=50000):
    """Fetch deep history directly from OKX with pagination.

    This is intentionally online/on-demand so backtesting is not limited by the
    user's local disk or CPU. The cap is a safety/cost/rate-limit guardrail, not
    a data-model limitation and can be raised for cloud research jobs.
    """
    wanted = max(100, min(int(bars), int(max_bars)))
    collected = []
    after = None
    seen_oldest = None

    while len(collected) < wanted:
        page_size = min(100, wanted - len(collected))
        params = {"instId": symbol, "bar": bar, "limit": str(page_size)}
        if after:
            params["after"] = after

        rows = okx_get("/api/v5/market/history-candles", params)
        if not rows:
            break

        collected.extend(rows)
        oldest = min(int(r[0]) for r in rows)
        if seen_oldest is not None and oldest >= seen_oldest:
            break
        seen_oldest = oldest
        after = str(oldest)

        if len(rows) < page_size:
            break

        time.sleep(0.12)

    timestamps = [int(row[0]) for row in collected]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate candles across history pages")
    rows = [row for row in sorted(collected, key=lambda row: int(row[0]), reverse=True)][:wanted]
    return normalize_candles(rows, bar=bar)


def get_derivatives(base):
    inst = f"{base}-USDT-SWAP"
    out = {"swap_available": False, "funding_rate": None, "open_interest": None}
    try:
        fr = okx_get("/api/v5/public/funding-rate", {"instId": inst})
        if fr:
            out["funding_rate"] = f(fr[0].get("fundingRate"), None)
            out["swap_available"] = True
    except Exception as exc:
        log.info("Funding unavailable for %s: %s", inst, type(exc).__name__)
    try:
        oi = okx_get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": inst})
        if oi:
            out["open_interest"] = f(oi[0].get("oiCcy") or oi[0].get("oi"), None)
            out["swap_available"] = True
    except Exception as exc:
        log.info("Open interest unavailable for %s: %s", inst, type(exc).__name__)
    return out


def build_universe():
    rows = []
    for t in get_spot_tickers():
        inst = str(t.get("instId", ""))
        if not inst.endswith("-USDT"):
            continue
        base = inst.split("-")[0]
        if base in STABLE_BASES:
            continue
        last = f(t.get("last"))
        open24 = f(t.get("open24h"))
        bid = f(t.get("bidPx"))
        ask = f(t.get("askPx"))
        qv = f(t.get("volCcy24h"))
        if qv <= 0:
            qv = f(t.get("vol24h")) * max(last, 0)
        if last <= 0 or qv < MIN_QUOTE_VOLUME:
            continue
        spread_bps = ((ask - bid) / last * 10000.0) if bid > 0 and ask > 0 else 999
        if spread_bps > MAX_SPREAD_BPS:
            continue
        change24 = pct_change(open24, last) if open24 > 0 else 0.0
        activity = (
            __import__("math").log10(max(qv, 1)) * 0.65
            + abs(change24) * 0.25
            - min(spread_bps, 50) * 0.03
        )
        rows.append({
            "symbol": inst, "base": base, "last": last,
            "quote_volume_24h": qv, "change_24h_pct": change24,
            "spread_bps": spread_bps, "activity_score": activity
        })
    rows.sort(key=lambda x: x["activity_score"], reverse=True)
    return rows[:UNIVERSE_SIZE]

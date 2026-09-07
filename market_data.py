import logging
import time
from datetime import datetime, timezone, timedelta
import httpx

from config import (
    BINANCE_FUTURES_BASE, BINANCE_SPOT_BASE, MARKET_DATA_MAX_AGE_SECONDS,
    MAX_SPREAD_BPS, MIN_QUOTE_VOLUME, OKX_BASE,
    ORDER_BOOK_DEPTH, ORDER_BOOK_MAX_SPREAD_BPS, ORDER_BOOK_MIN_LEVELS,
    PRICE_CONSENSUS_MAX_DEVIATION_BPS, PRICE_CONSENSUS_MIN_SOURCES,
    STABLE_BASES, UNIVERSE_SIZE,
)
from market_intelligence import cross_exchange_order_book, derivatives_summary, order_book_summary, price_consensus
from utils import f, pct_change

log = logging.getLogger(__name__)
http = httpx.Client(timeout=25.0, follow_redirects=True)


def okx_get(path, params=None):
    r = http.get(f"{OKX_BASE}{path}", params=params or {})
    r.raise_for_status()
    obj = r.json()
    if str(obj.get("code", "0")) != "0":
        raise RuntimeError(f"OKX error {obj.get('code')}: {obj.get('msg')}")
    return obj.get("data", [])


def get_spot_tickers():
    return okx_get("/api/v5/market/tickers", {"instType": "SPOT"})


def _binance_get(base_url, path, params=None):
    r = http.get(f"{base_url}{path}", params=params or {})
    r.raise_for_status()
    return r.json()


def get_binance_spot_prices():
    """One batch request keeps cross-exchange validation cheap for the universe."""
    rows = _binance_get(BINANCE_SPOT_BASE, "/api/v3/ticker/price")
    observed_ms = int(time.time() * 1000)
    return {
        str(row.get("symbol")): {"price": f(row.get("price")), "observed_ms": observed_ms}
        for row in rows if isinstance(row, dict)
    }


def normalize_candles(rows):
    out = []
    for row in reversed(rows):
        if len(row) < 6:
            continue
        confirm = str(row[8]) if len(row) > 8 else "1"
        if confirm == "0":
            continue
        out.append({
            "ts": int(row[0]),
            "open": f(row[1]),
            "high": f(row[2]),
            "low": f(row[3]),
            "close": f(row[4]),
            "volume": f(row[5]),
            "quote_volume": f(row[7]) if len(row) > 7 else 0.0,
        })
    return out


def get_candles(symbol, bar="15m", limit=120):
    rows = okx_get("/api/v5/market/candles", {
        "instId": symbol, "bar": bar, "limit": str(min(limit, 300))
    })
    return normalize_candles(rows)


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

    by_ts = {int(r[0]): r for r in collected}
    rows = [by_ts[k] for k in sorted(by_ts.keys(), reverse=True)][:wanted]
    return normalize_candles(rows)


def get_derivatives(base):
    inst = f"{base}-USDT-SWAP"
    exchange_rows = []
    okx_row = {"exchange": "okx", "funding_rate": None, "open_interest_base": None}
    try:
        fr = okx_get("/api/v5/public/funding-rate", {"instId": inst})
        if fr:
            okx_row["funding_rate"] = f(fr[0].get("fundingRate"), None)
    except Exception as exc:
        log.info("Funding unavailable for %s: %s", inst, type(exc).__name__)
    try:
        oi = okx_get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": inst})
        if oi:
            okx_row["open_interest_base"] = f(oi[0].get("oiCcy"), None)
    except Exception as exc:
        log.info("Open interest unavailable for %s: %s", inst, type(exc).__name__)
    if okx_row["funding_rate"] is not None or okx_row["open_interest_base"] is not None:
        exchange_rows.append(okx_row)

    binance_row = {"exchange": "binance", "funding_rate": None, "open_interest_base": None}
    symbol = f"{base}USDT"
    try:
        premium = _binance_get(BINANCE_FUTURES_BASE, "/fapi/v1/premiumIndex", {"symbol": symbol})
        binance_row["funding_rate"] = f(premium.get("lastFundingRate"), None)
    except Exception as exc:
        log.info("Binance funding unavailable for %s: %s", symbol, type(exc).__name__)
    try:
        oi = _binance_get(BINANCE_FUTURES_BASE, "/fapi/v1/openInterest", {"symbol": symbol})
        binance_row["open_interest_base"] = f(oi.get("openInterest"), None)
    except Exception as exc:
        log.info("Binance open interest unavailable for %s: %s", symbol, type(exc).__name__)
    if binance_row["funding_rate"] is not None or binance_row["open_interest_base"] is not None:
        exchange_rows.append(binance_row)

    liquidation_rows = []
    try:
        raw = okx_get("/api/v5/public/liquidation-orders", {"instType": "SWAP", "instId": inst})
        for group in raw:
            for detail in group.get("details", []):
                liquidation_rows.append({
                    "side": detail.get("side"), "price": detail.get("bkPx"), "size": detail.get("sz")
                })
    except Exception as exc:
        log.info("Liquidations unavailable for %s: %s", inst, type(exc).__name__)
    out = derivatives_summary(exchange_rows, liquidation_rows)
    out["swap_available"] = bool(exchange_rows)
    return out


def get_order_book_intelligence(base):
    """Two-exchange spot depth snapshot; evidence only, never trade authority."""
    books = []
    inst = f"{base}-USDT"
    try:
        rows = okx_get("/api/v5/market/books", {"instId": inst, "sz": str(ORDER_BOOK_DEPTH)})
        if rows:
            summary = order_book_summary(
                rows[0].get("bids"), rows[0].get("asks"), ORDER_BOOK_MIN_LEVELS, ORDER_BOOK_MAX_SPREAD_BPS
            )
            books.append({"exchange": "okx", **summary})
    except Exception as exc:
        log.info("OKX order book unavailable for %s: %s", inst, type(exc).__name__)
    try:
        row = _binance_get(BINANCE_SPOT_BASE, "/api/v3/depth", {
            "symbol": f"{base}USDT", "limit": str(ORDER_BOOK_DEPTH)
        })
        summary = order_book_summary(
            row.get("bids"), row.get("asks"), ORDER_BOOK_MIN_LEVELS, ORDER_BOOK_MAX_SPREAD_BPS
        )
        books.append({"exchange": "binance", **summary})
    except Exception as exc:
        log.info("Binance order book unavailable for %s: %s", base, type(exc).__name__)
    return cross_exchange_order_book(books)


def build_universe():
    try:
        binance_prices = get_binance_spot_prices()
    except Exception as exc:
        log.warning("Cross-exchange price batch unavailable: %s", type(exc).__name__)
        binance_prices = {}
    observed_ms = int(time.time() * 1000)
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
        quotes = [{"exchange": "okx", "price": last, "observed_ms": int(f(t.get("ts"), observed_ms))}]
        external = binance_prices.get(f"{base}USDT")
        if external:
            quotes.append({"exchange": "binance", **external})
        consensus = price_consensus(
            quotes,
            min_sources=PRICE_CONSENSUS_MIN_SOURCES,
            max_deviation_bps=PRICE_CONSENSUS_MAX_DEVIATION_BPS,
            max_age_seconds=MARKET_DATA_MAX_AGE_SECONDS,
            now_ms=observed_ms,
        )
        rows.append({
            "symbol": inst, "base": base, "last": last,
            "quote_volume_24h": qv, "change_24h_pct": change24,
            "spread_bps": spread_bps, "activity_score": activity,
            "market_consensus": consensus,
        })
    rows.sort(key=lambda x: x["activity_score"], reverse=True)
    return rows[:UNIVERSE_SIZE]

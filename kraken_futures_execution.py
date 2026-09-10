import math
import time
from dataclasses import dataclass

import httpx

FUTURES_REST = "https://futures.kraken.com/derivatives/api/v3"
FUTURES_CHARTS = "https://futures.kraken.com/api/charts/v1"
FUTURES_TAKER_FEE_BPS = 5.0
FUTURES_FEE_MODEL = "KRAKEN_FUTURES_TIER1_CONSERVATIVE"
PERP_HORIZON_HOURS = 168
MAX_BOOK_AGE_MS = 30_000
MAX_FUNDING_AGE_SECONDS = 2 * 3600

http = httpx.Client(timeout=12.0, follow_redirects=True)


@dataclass(frozen=True)
class KrakenFuturesExecution:
    executable: bool
    reason: str
    symbol: str
    perp_symbol: str | None
    requested_notional: float
    raw_vwap: float | None
    fill_price: float | None
    fee_bps: float
    visible_notional: float | None
    levels_used: int
    observed_ms: int | None
    source_count: int
    worst_slippage_bps: float | None
    supported_notional: float | None
    funding_rate_hourly: float | None = None
    funding_reserve_bps: float | None = None


def _finite_positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _base_asset(spot_symbol):
    base = str(spot_symbol or "").upper().split("-")[0].strip()
    if base == "BTC":
        base = "XBT"
    return base


def _fetch_instruments():
    r = http.get(f"{FUTURES_REST}/instruments", headers={"Accept": "application/json"})
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("instruments") or []
    return rows if isinstance(rows, list) else []


def resolve_perpetual(spot_symbol):
    base = _base_asset(spot_symbol)
    if not base:
        return None, None
    preferred = (f"PF_{base}USD", f"PI_{base}USD")
    instruments = _fetch_instruments()
    by_symbol = {str(row.get("symbol") or "").upper(): row for row in instruments if isinstance(row, dict)}
    for candidate in preferred:
        row = by_symbol.get(candidate)
        if not row:
            continue
        tradeable = row.get("tradeable")
        if tradeable is False:
            continue
        contract_size = _finite_positive(
            row.get("contractSize")
            or row.get("contract_size")
            or row.get("contractValue")
            or row.get("contract_value")
        )
        if contract_size is None:
            continue
        return candidate, contract_size
    return None, None


def _parse_level(level):
    if isinstance(level, dict):
        price = _finite_positive(level.get("price"))
        qty = _finite_positive(level.get("qty") or level.get("size"))
    elif isinstance(level, (list, tuple)) and len(level) >= 2:
        price = _finite_positive(level[0])
        qty = _finite_positive(level[1])
    else:
        return None
    return (price, qty) if price is not None and qty is not None else None


def _fetch_book(perp_symbol):
    r = http.get(
        f"{FUTURES_REST}/orderbook",
        headers={"Accept": "application/json"},
        params={"symbol": perp_symbol},
    )
    r.raise_for_status()
    payload = r.json()
    book = payload.get("orderBook") or payload.get("orderbook") or payload
    if not isinstance(book, dict):
        raise RuntimeError("Malformed Kraken Futures order book")
    bids = [_parse_level(x) for x in (book.get("bids") or [])]
    asks = [_parse_level(x) for x in (book.get("asks") or [])]
    bids = [x for x in bids if x]
    asks = [x for x in asks if x]
    if not bids or not asks:
        raise RuntimeError("One-sided Kraken Futures order book")
    bids.sort(key=lambda x: x[0], reverse=True)
    asks.sort(key=lambda x: x[0])
    if bids[0][0] >= asks[0][0]:
        raise RuntimeError("Crossed Kraken Futures order book")
    observed_ms = int(time.time() * 1000)
    server_time = payload.get("serverTime")
    if server_time:
        try:
            dt = __import__("datetime").datetime.fromisoformat(str(server_time).replace("Z", "+00:00"))
            observed_ms = int(dt.timestamp() * 1000)
        except (TypeError, ValueError):
            pass
    if int(time.time() * 1000) - observed_ms > MAX_BOOK_AGE_MS:
        raise RuntimeError("Stale Kraken Futures order book")
    return bids, asks, observed_ms


def _latest_funding_rate(perp_symbol):
    now_s = int(time.time())
    r = http.get(
        f"{FUTURES_CHARTS}/analytics/{perp_symbol}/funding",
        headers={"Accept": "application/json"},
        params={"since": now_s - 3 * 3600, "to": now_s, "interval": 3600},
    )
    r.raise_for_status()
    payload = r.json()
    result = payload.get("result") or payload
    timestamps = result.get("timestamp") or []
    data = result.get("data") or {}
    rates = data.get("rate") or []
    if not timestamps or not rates:
        raise RuntimeError("Missing Kraken Futures funding evidence")
    ts = int(timestamps[-1])
    if ts > 10_000_000_000:
        ts //= 1000
    if now_s - ts > MAX_FUNDING_AGE_SECONDS:
        raise RuntimeError("Stale Kraken Futures funding evidence")
    bar = rates[-1]
    values = bar if isinstance(bar, (list, tuple)) else [bar]
    parsed = []
    for value in values:
        try:
            x = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            parsed.append(x)
    if not parsed:
        raise RuntimeError("Malformed Kraken Futures funding evidence")
    # Funding analytics are hourly. Never assume a funding credit: reserve the
    # largest absolute rate observed in the latest OHLC funding bucket.
    return max(parsed, key=abs)


def _walk_book(levels, contract_size, requested_notional):
    remaining = float(requested_notional)
    quote = 0.0
    base = 0.0
    visible = 0.0
    used = 0
    for price, contracts in levels:
        level_base = contracts * contract_size
        level_notional = level_base * price
        visible += level_notional
        if remaining <= 0:
            continue
        take_notional = min(remaining, level_notional)
        take_base = take_notional / price
        quote += take_notional
        base += take_base
        remaining -= take_notional
        used += 1
    if remaining > max(1e-6, requested_notional * 1e-9) or base <= 0:
        return None, visible, used
    return quote / base, visible, used


def simulate_kraken_perp_fill(spot_symbol, direction, requested_notional, reserve_full_horizon_funding=False):
    direction = str(direction or "").upper()
    try:
        requested = float(requested_notional)
    except (TypeError, ValueError):
        requested = 0.0
    if direction not in {"LONG", "SHORT"} or not math.isfinite(requested) or requested <= 0:
        return KrakenFuturesExecution(False, "invalid_request", str(spot_symbol), None, requested, None, None, FUTURES_TAKER_FEE_BPS, None, 0, None, 0, None, None)
    try:
        perp_symbol, contract_size = resolve_perpetual(spot_symbol)
        if not perp_symbol or contract_size is None:
            raise RuntimeError("No tradeable Kraken perpetual with contract-size evidence")
        bids, asks, observed_ms = _fetch_book(perp_symbol)
        levels = bids if direction == "SHORT" else asks
        raw, visible, used = _walk_book(levels, contract_size, requested)
        if raw is None:
            raise RuntimeError("Insufficient visible Kraken Futures depth")
        best = levels[0][0]
        fee = FUTURES_TAKER_FEE_BPS / 10000.0
        funding_rate = None
        funding_reserve_bps = 0.0
        carry = 0.0
        source_count = 1
        if reserve_full_horizon_funding:
            funding_rate = _latest_funding_rate(perp_symbol)
            carry = abs(float(funding_rate)) * PERP_HORIZON_HOURS
            funding_reserve_bps = carry * 10000.0
            source_count = 2
        if direction == "SHORT":
            fill = raw * (1.0 - fee - carry)
            slippage_bps = max(0.0, (best - raw) / best * 10000.0)
        else:
            fill = raw * (1.0 + fee)
            slippage_bps = max(0.0, (raw - best) / best * 10000.0)
        if not math.isfinite(fill) or fill <= 0:
            raise RuntimeError("Funding/fee reserve makes perpetual fill invalid")
        return KrakenFuturesExecution(
            True, "kraken_perp_visible_depth_with_conservative_funding", str(spot_symbol), perp_symbol,
            requested, raw, fill, FUTURES_TAKER_FEE_BPS, visible, used, observed_ms,
            source_count, slippage_bps, visible, funding_rate, funding_reserve_bps,
        )
    except Exception as exc:
        return KrakenFuturesExecution(
            False, str(exc)[:180], str(spot_symbol), None, requested, None, None,
            FUTURES_TAKER_FEE_BPS, None, 0, None, 0, None, None,
        )

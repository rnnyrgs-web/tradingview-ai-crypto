"""Kraken Pro spot execution and fee model for forward-only paper trading.

Public market data only. No credentials, private endpoints, order placement, or
broker authority. If the requested market or visible depth is unavailable, the
caller must fail closed rather than substitute another venue.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import httpx

KRAKEN_API_BASE = "https://api.kraken.com"
KRAKEN_FEE_SCHEDULE_AS_OF = "2026-09-05"

# Official Kraken Pro spot taker schedule, expressed in basis points. Paper
# trading defaults to Tier 1 unless an account-specific tier is explicitly and
# independently verified. Using Tier 1 is conservative: it cannot make P&L look
# better merely because the real account may qualify for a lower fee.
SPOT_TAKER_BPS = {
    "tier1": 80.0,
    "tier2": 60.0,
    "tier3": 38.0,
    "tier4": 35.0,
    "tier5": 30.0,
    "tier6": 25.0,
    "tier7": 22.0,
    "tier8": 20.0,
    "tier9": 18.0,
    "tier10": 15.0,
    "tier11": 12.0,
    "tier12": 10.0,
    "pro1": 9.0,
    "pro2": 8.0,
    "pro3": 7.0,
    "pro4": 6.0,
    "pro5": 5.0,
}

# Stablecoin/pegged/FX schedule applies when the stablecoin is the base asset,
# to stablecoin-stablecoin/FX/pegged markets. The production universe currently
# excludes stable bases, but the classification is kept explicit and testable.
STABLE_FX_TAKER_BPS_TIER1 = 20.0
STABLE_BASES = {"USDT", "USDC", "DAI", "PYUSD", "EURT", "USDG", "USDE"}
FIAT_BASES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF"}
USD_BRIDGE_QUOTES = {"USDT", "USDC"}

_http = httpx.Client(timeout=httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=8.0), follow_redirects=True)


@dataclass(frozen=True)
class KrakenExecution:
    executable: bool
    reason: str
    symbol: str
    requested_notional: float
    raw_vwap: float | None
    fill_price: float | None
    fee_bps: float
    visible_notional: float
    levels_used: int
    observed_ms: int
    source_count: int = 1
    worst_slippage_bps: float | None = None
    supported_notional: float | None = None


def _split_symbol(symbol: str):
    parts = str(symbol or "").upper().replace("/", "-").split("-")
    if len(parts) != 2 or not all(parts):
        raise ValueError("invalid_symbol")
    return parts[0], parts[1]


def kraken_taker_fee_bps(symbol: str, tier: str = "tier1") -> float:
    base, quote = _split_symbol(symbol)
    if base in STABLE_BASES or (base in FIAT_BASES and quote in FIAT_BASES):
        # Conservative base schedule for stablecoin/FX markets. We intentionally
        # do not infer a lower volume tier without account-specific evidence.
        return STABLE_FX_TAKER_BPS_TIER1
    key = str(tier or "tier1").lower().replace("_", "")
    if key not in SPOT_TAKER_BPS:
        raise ValueError("unverified_kraken_fee_tier")
    return SPOT_TAKER_BPS[key]


def _kraken_pair_candidates(base: str, quote: str):
    aliases = {"BTC": "XBT", "DOGE": "XDG"}
    b = aliases.get(base, base)
    candidates = [f"{b}{quote}", f"{base}{quote}"]
    out = []
    for c in candidates:
        if c not in out:
            out.append(c)
    return out


def _fetch_depth(base: str, quote: str, count: int = 500):
    last_error = "kraken_market_unavailable"
    for pair in _kraken_pair_candidates(base, quote):
        for attempt in range(2):
            try:
                response = _http.get(f"{KRAKEN_API_BASE}/0/public/Depth", params={"pair": pair, "count": int(count)})
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError, TypeError):
                last_error = "kraken_depth_request_failed"
                if attempt == 0:
                    time.sleep(0.15)
                continue
            errors = payload.get("error") or []
            if errors:
                last_error = "kraken_pair_unavailable"
                break
            result = payload.get("result") or {}
            if not result:
                last_error = "kraken_empty_depth"
                if attempt == 0:
                    time.sleep(0.15)
                continue
            book = next(iter(result.values()))
            return pair, book
    raise RuntimeError(last_error)


def _walk(levels, requested_notional: float):
    remaining = float(requested_notional)
    base_qty = 0.0
    quote_spent = 0.0
    visible = 0.0
    used = 0
    for row in levels or []:
        try:
            price = float(row[0])
            qty = float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (math.isfinite(price) and math.isfinite(qty) and price > 0 and qty > 0):
            continue
        level_notional = price * qty
        visible += level_notional
        if remaining <= 1e-9:
            continue
        take_notional = min(remaining, level_notional)
        take_qty = take_notional / price
        base_qty += take_qty
        quote_spent += take_notional
        remaining -= take_notional
        used += 1
    if remaining > max(0.01, requested_notional * 1e-9) or base_qty <= 0:
        return None, visible, used
    return quote_spent / base_qty, visible, used


def _top_price(book, side_key):
    try:
        value = float((book.get(side_key) or [])[0][0])
    except (TypeError, ValueError, IndexError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _slippage_bps(raw_vwap, top):
    if raw_vwap is None or top is None or top <= 0:
        return None
    return abs(float(raw_vwap) / float(top) - 1.0) * 10000.0


def _simulate_usd_bridge_long_liquidation(symbol: str, requested: float, base: str, quote: str, fee_tier: str):
    """Sell a crypto into USD, then convert USD proceeds into the requested stable quote.

    This fallback is intentionally liquidation-only (SHORT action). It is used when
    Kraken exposes a direct spot order book such as FET/USD but no FET/USDT order
    book. Both legs must have sufficient visible Kraken depth; otherwise it fails
    closed. No synthetic candle or midpoint is used as an executable price.
    """
    if quote not in USD_BRIDGE_QUOTES or base in STABLE_BASES or base in FIAT_BASES:
        return None
    try:
        _, base_usd_book = _fetch_depth(base, "USD")
        _, stable_usd_book = _fetch_depth(quote, "USD")
    except RuntimeError as exc:
        return KrakenExecution(False, f"usd_bridge_unavailable:{exc}", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    # Leg 1: sell the crypto into USD. requested is approximately the whole
    # position quote notional supplied by the caller, and the walked VWAP is used
    # only to derive the per-unit executable price. The final P&L still multiplies
    # that price by the exact paper quantity.
    raw_base_usd, base_visible, base_levels = _walk(base_usd_book.get("bids"), requested)
    if raw_base_usd is None:
        return KrakenExecution(False, "insufficient_kraken_visible_depth_usd_bridge_leg1", symbol, requested, None, None, 0.0, base_visible, base_levels, int(time.time() * 1000), source_count=2)

    base_fee_bps = kraken_taker_fee_bps(f"{base}-USD", fee_tier)
    base_net_usd = raw_base_usd * (1.0 - base_fee_bps / 10000.0)

    # Leg 2: buy the requested stablecoin with the USD proceeds. Buying USDT/USD
    # or USDC/USD consumes asks, and the stable/FX fee schedule is included.
    raw_stable_usd, bridge_visible, bridge_levels = _walk(stable_usd_book.get("asks"), requested)
    if raw_stable_usd is None:
        return KrakenExecution(False, "insufficient_kraken_visible_depth_usd_bridge_leg2", symbol, requested, None, None, 0.0, min(base_visible, bridge_visible), base_levels + bridge_levels, int(time.time() * 1000), source_count=2)

    bridge_fee_bps = kraken_taker_fee_bps(f"{quote}-USD", fee_tier)
    stable_cost_usd = raw_stable_usd * (1.0 + bridge_fee_bps / 10000.0)
    if stable_cost_usd <= 0:
        return KrakenExecution(False, "invalid_usd_bridge_price", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    raw_effective = raw_base_usd / raw_stable_usd
    fill_effective = base_net_usd / stable_cost_usd
    top_base = _top_price(base_usd_book, "bids")
    top_bridge = _top_price(stable_usd_book, "asks")
    slip1 = _slippage_bps(raw_base_usd, top_base)
    slip2 = _slippage_bps(raw_stable_usd, top_bridge)
    combined_slip = sum(x for x in (slip1, slip2) if x is not None)
    visible = min(base_visible, bridge_visible)
    observed_ms = int(time.time() * 1000)
    return KrakenExecution(
        True,
        "ok_kraken_usd_bridge_visible_depth_taker",
        symbol,
        requested,
        raw_effective,
        fill_effective,
        base_fee_bps + bridge_fee_bps,
        visible,
        base_levels + bridge_levels,
        observed_ms,
        source_count=2,
        worst_slippage_bps=combined_slip,
        supported_notional=visible,
    )


def simulate_kraken_market_fill(symbol: str, direction: str, requested_notional: float, fee_tier: str = "tier1") -> KrakenExecution:
    direction = str(direction or "").upper()
    try:
        requested = float(requested_notional)
        base, quote = _split_symbol(symbol)
        fee_bps = kraken_taker_fee_bps(symbol, fee_tier)
    except (TypeError, ValueError):
        return KrakenExecution(False, "invalid_request", str(symbol), 0.0, None, None, 0.0, 0.0, 0, int(time.time() * 1000))
    if direction not in {"LONG", "SHORT"} or not math.isfinite(requested) or requested <= 0:
        return KrakenExecution(False, "invalid_request", str(symbol), requested, None, None, fee_bps, 0.0, 0, int(time.time() * 1000))
    try:
        _, book = _fetch_depth(base, quote)
    except RuntimeError as exc:
        # Some Kraken Convert combinations do not expose a direct spot order book
        # even though both assets are individually tradable. For long-position
        # liquidation only, allow a fully visible two-leg Kraken route through USD.
        if direction == "SHORT":
            bridged = _simulate_usd_bridge_long_liquidation(str(symbol), requested, base, quote, fee_tier)
            if bridged is not None:
                return bridged
        return KrakenExecution(False, str(exc), str(symbol), requested, None, None, fee_bps, 0.0, 0, int(time.time() * 1000))

    # A LONG entry consumes asks. A SHORT action/long liquidation consumes bids.
    side_key = "asks" if direction == "LONG" else "bids"
    raw_vwap, visible, levels_used = _walk(book.get(side_key), requested)
    observed_ms = int(time.time() * 1000)
    if raw_vwap is None:
        return KrakenExecution(False, "insufficient_kraken_visible_depth", str(symbol), requested, None, None, fee_bps, visible, levels_used, observed_ms)

    fee_fraction = fee_bps / 10000.0
    fill = raw_vwap * (1.0 + fee_fraction if direction == "LONG" else 1.0 - fee_fraction)
    top = _top_price(book, side_key)
    slip = _slippage_bps(raw_vwap, top)
    return KrakenExecution(
        True,
        "ok_kraken_visible_depth_taker",
        str(symbol),
        requested,
        raw_vwap,
        fill,
        fee_bps,
        visible,
        levels_used,
        observed_ms,
        source_count=1,
        worst_slippage_bps=slip,
        supported_notional=visible,
    )

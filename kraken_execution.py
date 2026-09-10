"""Kraken Pro spot execution and fee model for forward-only paper trading.

Public market data only. No credentials, private endpoints, order placement, or
broker authority. If the requested market or visible depth is unavailable, the
caller must fail closed unless a fully visible two-leg Kraken USD route can be
verified on both legs.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import httpx

KRAKEN_API_BASE = "https://api.kraken.com"
KRAKEN_FEE_SCHEDULE_AS_OF = "2026-09-05"

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


def _simulate_usd_bridge_long_entry(symbol: str, requested: float, base: str, quote: str, fee_tier: str):
    """Buy crypto using a visible quote->USD->crypto route on Kraken.

    This is used only when Kraken has no direct BASE/USDT or BASE/USDC book.
    Both public order books must exist and have enough visible depth. The returned
    effective fill includes taker fees on both legs and therefore cannot make the
    paper result look better than the observable two-leg route.
    """
    if quote not in USD_BRIDGE_QUOTES or base in STABLE_BASES or base in FIAT_BASES:
        return None
    try:
        _, stable_usd_book = _fetch_depth(quote, "USD")
        _, base_usd_book = _fetch_depth(base, "USD")
    except RuntimeError as exc:
        return KrakenExecution(False, f"usd_bridge_unavailable:{exc}", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    stable_bid = _top_price(stable_usd_book, "bids")
    if stable_bid is None:
        return KrakenExecution(False, "invalid_usd_bridge_quote_book", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    # requested is denominated in the stable quote. Convert that quantity into an
    # approximate USD notional for the depth walker using the observable best bid.
    stable_target_usd = requested * stable_bid
    raw_stable_usd, stable_visible_usd, stable_levels = _walk(stable_usd_book.get("bids"), stable_target_usd)
    if raw_stable_usd is None:
        return KrakenExecution(False, "insufficient_kraken_visible_depth_usd_bridge_leg1", symbol, requested, None, None, 0.0, stable_visible_usd, stable_levels, int(time.time() * 1000), source_count=2)

    stable_fee_bps = kraken_taker_fee_bps(f"{quote}-USD", fee_tier)
    usd_per_quote_after_fee = raw_stable_usd * (1.0 - stable_fee_bps / 10000.0)
    if usd_per_quote_after_fee <= 0:
        return KrakenExecution(False, "invalid_usd_bridge_price", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    available_usd = requested * usd_per_quote_after_fee
    raw_base_usd, base_visible_usd, base_levels = _walk(base_usd_book.get("asks"), available_usd)
    if raw_base_usd is None:
        supported_quote = min(stable_visible_usd, base_visible_usd) / max(raw_stable_usd, 1e-12)
        return KrakenExecution(False, "insufficient_kraken_visible_depth_usd_bridge_leg2", symbol, requested, None, None, 0.0, min(stable_visible_usd, base_visible_usd), stable_levels + base_levels, int(time.time() * 1000), source_count=2, supported_notional=supported_quote)

    base_fee_bps = kraken_taker_fee_bps(f"{base}-USD", fee_tier)
    raw_effective = raw_base_usd / raw_stable_usd
    fill_effective = raw_base_usd * (1.0 + base_fee_bps / 10000.0) / usd_per_quote_after_fee
    top_base = _top_price(base_usd_book, "asks")
    slip1 = _slippage_bps(raw_stable_usd, stable_bid)
    slip2 = _slippage_bps(raw_base_usd, top_base)
    combined_slip = sum(x for x in (slip1, slip2) if x is not None)
    supported_quote = min(stable_visible_usd, base_visible_usd) / max(raw_stable_usd, 1e-12)
    observed_ms = int(time.time() * 1000)
    return KrakenExecution(
        True,
        "ok_kraken_usd_bridge_visible_depth_taker_entry",
        symbol,
        requested,
        raw_effective,
        fill_effective,
        stable_fee_bps + base_fee_bps,
        min(stable_visible_usd, base_visible_usd),
        stable_levels + base_levels,
        observed_ms,
        source_count=2,
        worst_slippage_bps=combined_slip,
        supported_notional=supported_quote,
    )


def _simulate_usd_bridge_long_liquidation(symbol: str, requested: float, base: str, quote: str, fee_tier: str):
    """Sell a crypto into USD, then convert USD proceeds into the requested stable quote."""
    if quote not in USD_BRIDGE_QUOTES or base in STABLE_BASES or base in FIAT_BASES:
        return None
    try:
        _, base_usd_book = _fetch_depth(base, "USD")
        _, stable_usd_book = _fetch_depth(quote, "USD")
    except RuntimeError as exc:
        return KrakenExecution(False, f"usd_bridge_unavailable:{exc}", symbol, requested, None, None, 0.0, 0.0, 0, int(time.time() * 1000), source_count=2)

    raw_base_usd, base_visible, base_levels = _walk(base_usd_book.get("bids"), requested)
    if raw_base_usd is None:
        return KrakenExecution(False, "insufficient_kraken_visible_depth_usd_bridge_leg1", symbol, requested, None, None, 0.0, base_visible, base_levels, int(time.time() * 1000), source_count=2)

    base_fee_bps = kraken_taker_fee_bps(f"{base}-USD", fee_tier)
    base_net_usd = raw_base_usd * (1.0 - base_fee_bps / 10000.0)

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
        bridged = None
        if direction == "LONG":
            bridged = _simulate_usd_bridge_long_entry(str(symbol), requested, base, quote, fee_tier)
        elif direction == "SHORT":
            bridged = _simulate_usd_bridge_long_liquidation(str(symbol), requested, base, quote, fee_tier)
        if bridged is not None:
            return bridged
        return KrakenExecution(False, str(exc), str(symbol), requested, None, None, fee_bps, 0.0, 0, int(time.time() * 1000))

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

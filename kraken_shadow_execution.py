"""Broker-disconnected Kraken shadow execution using public order-book snapshots only.

This module intentionally contains no authentication, private endpoints, order
placement, cancellation, or credential handling. It estimates a hypothetical
market fill from a genuine public Kraken book supplied by the caller. Current
book state is execution evidence only and must never be used as historical/OOS
strategy evidence.
"""

from dataclasses import dataclass, asdict
import math
import time


MAX_BOOK_AGE_SECONDS = 15.0
MAX_FUTURE_SKEW_SECONDS = 5.0


@dataclass(frozen=True)
class KrakenShadowFill:
    executable: bool
    reason: str
    pair: str
    direction: str
    requested_notional: float
    filled_notional: float
    filled_base: float
    vwap: float | None
    best_price: float | None
    slippage_bps: float | None
    fee_bps: float
    after_fee_fill_price: float | None
    observed_ms: int | None
    source: str = "kraken_public_order_book"
    shadow_only: bool = True
    broker_connected: bool = False
    order_authority: bool = False
    trade_authority: bool = False

    def to_dict(self):
        return asdict(self)


def _positive(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def _levels(rows, reverse=False):
    out = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        price = _positive(row[0])
        size = _positive(row[1])
        if price is not None and size is not None:
            out.append((price, size))
    return sorted(out, key=lambda item: item[0], reverse=reverse)


def shadow_market_fill(pair, direction, requested_notional, book, *, fee_bps=0.0, now_ms=None, max_age_seconds=MAX_BOOK_AGE_SECONDS):
    """Estimate a hypothetical Kraken market fill without placing an order.

    `book` must be a timestamped public snapshot with `asks`, `bids`, and
    `observed_ms`. LONG consumes asks; SHORT consumes bids. No hidden depth is
    extrapolated: insufficient visible depth fails closed.
    """
    direction = str(direction or "").upper()
    requested = _positive(requested_notional)
    pair = str(pair or "").strip().upper()
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    try:
        fee = float(fee_bps)
    except (TypeError, ValueError):
        fee = -1.0

    def fail(reason, observed_ms=None):
        return KrakenShadowFill(False, reason, pair, direction, float(requested or 0.0), 0.0, 0.0, None, None, None, max(0.0, fee), None, observed_ms)

    if not pair or direction not in {"LONG", "SHORT"} or requested is None:
        return fail("invalid_request")
    if not math.isfinite(fee) or fee < 0:
        return fail("invalid_fee")
    if not isinstance(book, dict):
        return fail("missing_public_book")
    try:
        observed_ms = int(book.get("observed_ms"))
    except (TypeError, ValueError):
        return fail("missing_book_timestamp")
    age_seconds = (now_ms - observed_ms) / 1000.0
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        return fail("future_book_timestamp", observed_ms)
    if age_seconds > float(max_age_seconds):
        return fail("stale_public_book", observed_ms)

    levels = _levels(book.get("asks") if direction == "LONG" else book.get("bids"), reverse=direction == "SHORT")
    if not levels:
        return fail("empty_public_book", observed_ms)

    remaining_quote = requested
    filled_quote = 0.0
    filled_base = 0.0
    best_price = levels[0][0]
    for price, available_base in levels:
        level_quote = price * available_base
        take_quote = min(remaining_quote, level_quote)
        take_base = take_quote / price
        filled_quote += take_quote
        filled_base += take_base
        remaining_quote -= take_quote
        if remaining_quote <= max(1e-9, requested * 1e-12):
            break

    if remaining_quote > max(1e-9, requested * 1e-12) or filled_base <= 0:
        return KrakenShadowFill(False, "insufficient_visible_kraken_depth", pair, direction, requested, filled_quote, filled_base, None, best_price, None, fee, None, observed_ms)

    vwap = filled_quote / filled_base
    if direction == "LONG":
        slippage_bps = max(0.0, (vwap - best_price) / best_price * 10000.0)
        after_fee = vwap * (1.0 + fee / 10000.0)
    else:
        slippage_bps = max(0.0, (best_price - vwap) / best_price * 10000.0)
        after_fee = vwap * (1.0 - fee / 10000.0)

    return KrakenShadowFill(True, "ok_shadow_public_book", pair, direction, requested, filled_quote, filled_base, vwap, best_price, slippage_bps, fee, after_fee, observed_ms)

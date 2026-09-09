"""Timestamp-safe Kraken public-book microstructure measurements for forward research.

This module is deliberately broker-disconnected and research-only. It summarizes
only the public order-book snapshot supplied by the caller at observation time.
It does not reconstruct historical books, infer hidden liquidity, place orders,
or grant signal/trade/promotion authority.
"""

import math
import time

from kraken_shadow_execution import MAX_BOOK_AGE_SECONDS, MAX_FUTURE_SKEW_SECONDS, _levels


def _finite_positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _base_result(pair, reason, observed_ms=None):
    return {
        "available": False,
        "reliable": False,
        "reason": reason,
        "pair": str(pair or "").strip().upper(),
        "observed_ms": observed_ms,
        "source": "kraken_public_order_book",
        "historical": False,
        "research_only": True,
        "broker_connected": False,
        "order_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }


def summarize_kraken_microstructure(
    pair,
    book,
    *,
    now_ms=None,
    max_age_seconds=MAX_BOOK_AGE_SECONDS,
    depth_levels=5,
):
    """Summarize a genuine timestamped Kraken public-book snapshot.

    Metrics are descriptive only and are intended to be persisted prospectively
    alongside future forecasts for later forward/OOS research. Missing, stale,
    future, crossed, malformed, or one-sided books fail closed. No unavailable
    historical order book is reconstructed.
    """
    pair = str(pair or "").strip().upper()
    if not pair:
        return _base_result(pair, "invalid_pair")
    if not isinstance(book, dict):
        return _base_result(pair, "missing_public_book")

    try:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    except (TypeError, ValueError, OverflowError):
        return _base_result(pair, "invalid_observation_clock")
    try:
        observed_ms = int(book.get("observed_ms"))
    except (TypeError, ValueError, OverflowError):
        return _base_result(pair, "missing_book_timestamp")

    try:
        age_seconds = (now_ms - observed_ms) / 1000.0
        max_age = float(max_age_seconds)
    except (TypeError, ValueError, OverflowError):
        return _base_result(pair, "invalid_age_policy", observed_ms)
    if not math.isfinite(age_seconds):
        return _base_result(pair, "invalid_book_timestamp", observed_ms)
    if not math.isfinite(max_age) or max_age < 0:
        return _base_result(pair, "invalid_age_policy", observed_ms)
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        return _base_result(pair, "future_book_timestamp", observed_ms)
    if age_seconds > max_age:
        return _base_result(pair, "stale_public_book", observed_ms)

    try:
        levels_wanted = int(depth_levels)
    except (TypeError, ValueError, OverflowError):
        return _base_result(pair, "invalid_depth_levels", observed_ms)
    if levels_wanted < 1 or levels_wanted > 100:
        return _base_result(pair, "invalid_depth_levels", observed_ms)

    bids = _levels(book.get("bids"), reverse=True)
    asks = _levels(book.get("asks"), reverse=False)
    if not bids or not asks:
        return _base_result(pair, "one_sided_or_empty_public_book", observed_ms)

    best_bid, best_bid_size = bids[0]
    best_ask, best_ask_size = asks[0]
    if best_bid >= best_ask:
        return _base_result(pair, "crossed_public_book", observed_ms)

    mid = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / mid * 10000.0

    bid_top = bids[:levels_wanted]
    ask_top = asks[:levels_wanted]
    bid_quote_depth = sum(price * size for price, size in bid_top)
    ask_quote_depth = sum(price * size for price, size in ask_top)
    total_quote_depth = bid_quote_depth + ask_quote_depth
    if not _finite_positive(total_quote_depth):
        return _base_result(pair, "invalid_visible_depth", observed_ms)

    depth_imbalance = (bid_quote_depth - ask_quote_depth) / total_quote_depth
    top_size_total = best_bid_size + best_ask_size
    top_level_imbalance = (
        (best_bid_size - best_ask_size) / top_size_total if top_size_total > 0 else 0.0
    )
    microprice = (
        best_ask * best_bid_size + best_bid * best_ask_size
    ) / top_size_total
    microprice_deviation_bps = (microprice - mid) / mid * 10000.0

    result = _base_result(pair, "ok", observed_ms)
    result.update({
        "available": True,
        "reliable": True,
        "age_seconds": age_seconds,
        "depth_levels_requested": levels_wanted,
        "bid_levels_used": len(bid_top),
        "ask_levels_used": len(ask_top),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid,
        "spread_bps": spread_bps,
        "best_bid_size": best_bid_size,
        "best_ask_size": best_ask_size,
        "top_level_imbalance": top_level_imbalance,
        "bid_visible_quote_depth": bid_quote_depth,
        "ask_visible_quote_depth": ask_quote_depth,
        "visible_quote_depth": total_quote_depth,
        "depth_imbalance": depth_imbalance,
        "microprice": microprice,
        "microprice_deviation_bps": microprice_deviation_bps,
        "hidden_liquidity_assumed": False,
    })
    return result

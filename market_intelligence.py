import statistics
import time

from utils import f


def price_consensus(quotes, min_sources=2, max_deviation_bps=50.0, max_age_seconds=120, now_ms=None):
    """Validate independent exchange quotes without silently accepting stale data."""
    now_ms = int(now_ms or time.time() * 1000)
    valid = []
    rejected = []
    for quote in quotes:
        exchange = str(quote.get("exchange", "unknown"))
        price = f(quote.get("price"), 0.0)
        observed_ms = int(f(quote.get("observed_ms"), 0.0))
        age_seconds = (now_ms - observed_ms) / 1000.0 if observed_ms else None
        if price <= 0:
            rejected.append({"exchange": exchange, "reason": "invalid_price"})
        elif age_seconds is not None and (age_seconds < -5 or age_seconds > max_age_seconds):
            rejected.append({"exchange": exchange, "reason": "stale_quote"})
        else:
            valid.append({"exchange": exchange, "price": price, "age_seconds": age_seconds})

    median = statistics.median(q["price"] for q in valid) if valid else None
    for quote in valid:
        quote["deviation_bps"] = abs(quote["price"] - median) / median * 10000.0
    price_range_bps = ((max(q["price"] for q in valid) - min(q["price"] for q in valid)) / median * 10000.0) if valid else None
    reliable = len(valid) >= min_sources and price_range_bps is not None and price_range_bps <= max_deviation_bps
    reason = "ok" if reliable else (
        "insufficient_sources" if len(valid) < min_sources else "exchange_price_disagreement"
    )
    return {
        "reliable": reliable,
        "reason": reason,
        "source_count": len(valid),
        "median_price": median,
        "max_deviation_bps": max((q["deviation_bps"] for q in valid), default=None),
        "price_range_bps": price_range_bps,
        "quotes": valid,
        "rejected": rejected,
    }


def derivatives_summary(exchange_rows, liquidation_rows=None):
    funding = [f(x.get("funding_rate"), None) for x in exchange_rows]
    funding = [x for x in funding if x is not None]
    median_funding = statistics.median(funding) if funding else None
    if median_funding is None:
        crowding = "UNKNOWN"
    elif median_funding >= 0.0005:
        crowding = "EXTREME_LONG"
    elif median_funding <= -0.0005:
        crowding = "EXTREME_SHORT"
    elif median_funding >= 0.0001:
        crowding = "LONG"
    elif median_funding <= -0.0001:
        crowding = "SHORT"
    else:
        crowding = "NEUTRAL"

    # Contract multipliers vary by instrument. Keep raw price*size pressure units
    # instead of falsely presenting the result as comparable USD notional.
    liq = {"available": False, "buy_pressure_units": 0.0, "sell_pressure_units": 0.0, "event_count": 0}
    for row in liquidation_rows or []:
        side = str(row.get("side", "")).lower()
        notional = f(row.get("price")) * f(row.get("size"))
        if side in {"buy", "sell"} and notional > 0:
            liq[f"{side}_pressure_units"] += notional
            liq["event_count"] += 1
    liq["available"] = liq["event_count"] > 0
    return {
        "reliable": len(funding) >= 2,
        "funding_source_count": len(funding),
        "median_funding_rate": median_funding,
        "funding_dispersion": max(funding) - min(funding) if len(funding) >= 2 else None,
        "crowding": crowding,
        "exchanges": exchange_rows,
        "liquidations": liq,
    }


def order_book_summary(bids, asks, min_levels=10, max_spread_bps=50.0):
    """Summarize one spot-book snapshot without predicting from it."""
    def levels(rows, reverse=False):
        clean = []
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            price, size = f(row[0]), f(row[1])
            if price > 0 and size > 0:
                clean.append((price, size))
        return sorted(clean, key=lambda x: x[0], reverse=reverse)

    clean_bids, clean_asks = levels(bids, True), levels(asks)
    if not clean_bids or not clean_asks:
        return {"reliable": False, "reason": "empty_book", "level_count": 0}
    best_bid, best_ask = clean_bids[0][0], clean_asks[0][0]
    mid = (best_bid + best_ask) / 2.0
    crossed = best_bid >= best_ask
    spread_bps = (best_ask - best_bid) / mid * 10000.0

    def depth(rows, boundary):
        return sum(price * size for price, size in rows if boundary(price))

    bid_10 = depth(clean_bids, lambda p: p >= mid * 0.999)
    ask_10 = depth(clean_asks, lambda p: p <= mid * 1.001)
    bid_25 = depth(clean_bids, lambda p: p >= mid * 0.9975)
    ask_25 = depth(clean_asks, lambda p: p <= mid * 1.0025)
    total_25 = bid_25 + ask_25
    imbalance = (bid_25 - ask_25) / total_25 if total_25 > 0 else None
    enough = len(clean_bids) >= min_levels and len(clean_asks) >= min_levels
    reliable = enough and not crossed and spread_bps <= max_spread_bps and total_25 > 0
    reason = "ok" if reliable else (
        "insufficient_levels" if not enough else "crossed_book" if crossed else
        "spread_too_wide" if spread_bps > max_spread_bps else "zero_depth"
    )
    return {
        "reliable": reliable, "reason": reason,
        "level_count": min(len(clean_bids), len(clean_asks)),
        "mid_price": mid, "spread_bps": spread_bps,
        "bid_depth_10bps": bid_10, "ask_depth_10bps": ask_10,
        "bid_depth_25bps": bid_25, "ask_depth_25bps": ask_25,
        "imbalance_25bps": imbalance,
    }


def cross_exchange_order_book(exchange_books):
    reliable = [x for x in exchange_books if x.get("reliable")]
    imbalances = [x["imbalance_25bps"] for x in reliable if x.get("imbalance_25bps") is not None]
    disagreement = len(imbalances) >= 2 and min(imbalances) < 0 < max(imbalances)
    return {
        "research_only": True,
        "reliable": len(reliable) >= 2,
        "reason": "ok" if len(reliable) >= 2 else "insufficient_reliable_exchanges",
        "exchange_count": len(reliable),
        "median_imbalance_25bps": statistics.median(imbalances) if imbalances else None,
        "direction_disagreement": disagreement,
        "exchanges": exchange_books,
    }

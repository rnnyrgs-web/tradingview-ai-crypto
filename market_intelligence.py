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

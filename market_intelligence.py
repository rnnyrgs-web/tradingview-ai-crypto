import statistics
import time

from utils import f


DEFAULT_FILL_NOTIONALS = (1000.0, 5000.0, 10000.0)


def price_consensus(quotes, min_sources=2, max_deviation_bps=50.0, max_age_seconds=120, now_ms=None):
    """Validate independent exchange quotes with explicit provenance and freshness.

    Source count is based on unique exchanges, so duplicate observations from a
    single venue can never masquerade as independent confirmation. For each
    exchange the freshest valid observation is retained. Reliability remains
    fail-closed: stale/missing sources or excessive cross-exchange disagreement
    cannot authorize a live action.
    """
    now_ms = int(now_ms or time.time() * 1000)
    accepted_by_exchange = {}
    rejected = []
    raw_source_names = []

    for quote in quotes or []:
        exchange = str(quote.get("exchange", "unknown")).strip().lower() or "unknown"
        raw_source_names.append(exchange)
        price = f(quote.get("price"), 0.0)
        observed_ms = int(f(quote.get("observed_ms"), 0.0))
        age_seconds = (now_ms - observed_ms) / 1000.0 if observed_ms else None
        if price <= 0:
            rejected.append({"exchange": exchange, "reason": "invalid_price"})
            continue
        if observed_ms <= 0:
            rejected.append({"exchange": exchange, "reason": "missing_timestamp"})
            continue
        if age_seconds < -5:
            rejected.append({"exchange": exchange, "reason": "future_quote"})
            continue
        if age_seconds > max_age_seconds:
            rejected.append({"exchange": exchange, "reason": "stale_quote", "age_seconds": age_seconds})
            continue

        current = accepted_by_exchange.get(exchange)
        candidate = {
            "exchange": exchange,
            "price": price,
            "observed_ms": observed_ms,
            "age_seconds": age_seconds,
        }
        if current is None or observed_ms > current["observed_ms"]:
            if current is not None:
                rejected.append({"exchange": exchange, "reason": "superseded_duplicate_quote"})
            accepted_by_exchange[exchange] = candidate
        else:
            rejected.append({"exchange": exchange, "reason": "duplicate_exchange_quote"})

    valid = list(accepted_by_exchange.values())
    median = statistics.median(q["price"] for q in valid) if valid else None
    for quote in valid:
        quote["deviation_bps"] = abs(quote["price"] - median) / median * 10000.0
    price_range_bps = (
        (max(q["price"] for q in valid) - min(q["price"] for q in valid)) / median * 10000.0
        if valid else None
    )
    unique_source_count = len(valid)
    reliable = (
        unique_source_count >= min_sources
        and price_range_bps is not None
        and price_range_bps <= max_deviation_bps
    )
    if reliable:
        reason = "ok"
    elif unique_source_count < min_sources:
        reason = "insufficient_independent_sources"
    else:
        reason = "exchange_price_disagreement"

    ages = [q["age_seconds"] for q in valid if q.get("age_seconds") is not None]
    max_age = max(ages) if ages else None
    freshness_ratio = 0.0
    if ages and max_age_seconds > 0:
        freshness_ratio = max(0.0, min(1.0, 1.0 - max_age / max_age_seconds))
    source_ratio = min(1.0, unique_source_count / max(1, int(min_sources)))

    # This multiplier is restrictive only. It is not a probability. A fully
    # reliable consensus retains 1.0; one fresh independent source can retain at
    # most 0.5 research confidence; explicit contradiction collapses to zero.
    if reliable:
        confidence_multiplier = 1.0
    elif reason == "exchange_price_disagreement":
        confidence_multiplier = 0.0
    elif unique_source_count == 1:
        confidence_multiplier = min(0.5, 0.5 * freshness_ratio)
    else:
        confidence_multiplier = 0.0

    return {
        "reliable": reliable,
        "reason": reason,
        "source_count": unique_source_count,
        "required_source_count": int(min_sources),
        "median_price": median,
        "max_deviation_bps": max((q["deviation_bps"] for q in valid), default=None),
        "price_range_bps": price_range_bps,
        "max_quote_age_seconds": max_age,
        "freshness_ratio": freshness_ratio,
        "source_ratio": source_ratio,
        "confidence_multiplier": confidence_multiplier,
        "quotes": valid,
        "rejected": rejected,
        "provenance": {
            "raw_observation_count": len(quotes or []),
            "raw_exchange_names": sorted(set(raw_source_names)),
            "accepted_exchange_names": sorted(accepted_by_exchange),
            "independent_source_count": unique_source_count,
            "max_age_seconds_policy": max_age_seconds,
            "max_deviation_bps_policy": max_deviation_bps,
        },
    }


def liquidation_evidence(liquidation_rows=None):
    """Summarize liquidation events without inventing USD notional.

    Contract multipliers differ by instrument and exchange. We therefore expose
    event counts, raw contract size and price*size pressure units only. The
    latter are explicitly labelled as non-USD, non-comparable pressure units.
    """
    out = {
        "research_only": True,
        "available": False,
        "event_count": 0,
        "buy_event_count": 0,
        "sell_event_count": 0,
        "buy_raw_size": 0.0,
        "sell_raw_size": 0.0,
        "buy_pressure_units": 0.0,
        "sell_pressure_units": 0.0,
        "pressure_units_are_usd": False,
        "reason": "no_valid_events",
    }
    for row in liquidation_rows or []:
        side = str(row.get("side", "")).lower()
        price = f(row.get("price"), 0.0)
        size = f(row.get("size"), 0.0)
        if side not in {"buy", "sell"} or price <= 0 or size <= 0:
            continue
        out["event_count"] += 1
        out[f"{side}_event_count"] += 1
        out[f"{side}_raw_size"] += size
        out[f"{side}_pressure_units"] += price * size
    if out["event_count"]:
        out["available"] = True
        out["reason"] = "ok_raw_contract_evidence"
    return out


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

    return {
        "reliable": len(funding) >= 2,
        "funding_source_count": len(funding),
        "median_funding_rate": median_funding,
        "funding_dispersion": max(funding) - min(funding) if len(funding) >= 2 else None,
        "crowding": crowding,
        "exchanges": exchange_rows,
        "liquidations": liquidation_evidence(liquidation_rows),
    }


def _clean_book_levels(rows, reverse=False):
    clean = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        price, size = f(row[0]), f(row[1])
        if price > 0 and size > 0:
            clean.append((price, size))
    return sorted(clean, key=lambda x: x[0], reverse=reverse)


def _simulate_quote_notional_fill(levels, quote_notional, mid_price, side):
    requested = max(0.0, f(quote_notional, 0.0))
    if requested <= 0 or mid_price <= 0 or side not in {"buy", "sell"}:
        return {"available": False, "reason": "invalid_request"}

    filled_base = 0.0
    filled_quote = 0.0
    target_base = requested / mid_price if side == "sell" else None

    for price, size in levels:
        if side == "buy":
            remaining_quote = requested - filled_quote
            if remaining_quote <= 0:
                break
            level_quote = price * size
            take_quote = min(remaining_quote, level_quote)
            take_base = take_quote / price
        else:
            remaining_base = target_base - filled_base
            if remaining_base <= 0:
                break
            take_base = min(remaining_base, size)
            take_quote = take_base * price
        filled_base += take_base
        filled_quote += take_quote

    if filled_base <= 0:
        return {"available": False, "reason": "no_fill"}

    if side == "buy":
        coverage = min(1.0, filled_quote / requested)
    else:
        coverage = min(1.0, filled_base / target_base) if target_base else 0.0
    vwap = filled_quote / filled_base
    slippage_bps = (
        (vwap - mid_price) / mid_price * 10000.0
        if side == "buy" else (mid_price - vwap) / mid_price * 10000.0
    )
    complete = coverage >= 0.999999
    return {
        "available": True,
        "complete_fill": complete,
        "coverage_ratio": coverage,
        "requested_quote_notional": requested,
        "filled_quote": filled_quote,
        "filled_base": filled_base,
        "vwap": vwap,
        "slippage_bps_vs_mid": max(0.0, slippage_bps),
        "reason": "ok" if complete else "insufficient_visible_depth",
    }


def live_fill_slippage_estimates(bids, asks, notionals=DEFAULT_FILL_NOTIONALS):
    clean_bids = _clean_book_levels(bids, True)
    clean_asks = _clean_book_levels(asks)
    if not clean_bids or not clean_asks or clean_bids[0][0] >= clean_asks[0][0]:
        return {"research_only": True, "available": False, "reason": "invalid_book", "estimates": []}
    mid = (clean_bids[0][0] + clean_asks[0][0]) / 2.0
    estimates = []
    for notional in notionals:
        requested = f(notional, 0.0)
        if requested <= 0:
            continue
        estimates.append({
            "quote_notional": requested,
            "buy": _simulate_quote_notional_fill(clean_asks, requested, mid, "buy"),
            "sell": _simulate_quote_notional_fill(clean_bids, requested, mid, "sell"),
        })
    return {
        "research_only": True,
        "available": bool(estimates),
        "reason": "ok_current_snapshot" if estimates else "no_valid_notionals",
        "mid_price": mid,
        "historical": False,
        "estimates": estimates,
    }


def order_book_summary(bids, asks, min_levels=10, max_spread_bps=50.0):
    clean_bids, clean_asks = _clean_book_levels(bids, True), _clean_book_levels(asks)
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
        "live_fill_slippage": live_fill_slippage_estimates(clean_bids, clean_asks),
    }


def cross_exchange_order_book(exchange_books):
    reliable = [x for x in exchange_books if x.get("reliable")]
    imbalances = [x["imbalance_25bps"] for x in reliable if x.get("imbalance_25bps") is not None]
    disagreement = len(imbalances) >= 2 and min(imbalances) < 0 < max(imbalances)
    slippage_available = sum(1 for x in reliable if x.get("live_fill_slippage", {}).get("available"))
    return {
        "research_only": True,
        "reliable": len(reliable) >= 2,
        "reason": "ok" if len(reliable) >= 2 else "insufficient_reliable_exchanges",
        "exchange_count": len(reliable),
        "median_imbalance_25bps": statistics.median(imbalances) if imbalances else None,
        "direction_disagreement": disagreement,
        "live_slippage_source_count": slippage_available,
        "exchanges": exchange_books,
    }

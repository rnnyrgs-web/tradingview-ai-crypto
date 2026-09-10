"""Research-only FFriZz V3 causal open-interest alignment challenger.

V2 tested exact equality between completed 1H candle endpoints and Binance OI
period-end timestamps. Live evidence showed zero exact overlap across the sampled
universe, and Binance documents OI timestamps as period-end timestamps without
requiring canonical wall-clock boundaries. V3 therefore tests one separate,
predeclared timestamp hypothesis: for each OI observation, use only the latest
completed candle endpoint at or before the OI timestamp, with staleness strictly
less than one bar.

This is a causal as-of lookup, not nearest-neighbour matching: future price
endpoints are forbidden. Missing/stale observations remain unavailable. The
challenger is research/shadow only and has no persistence, paper, promotion,
broker, or production authority.
"""

from __future__ import annotations

from bisect import bisect_right

from ffrizz_secondary_signals import (
    FIXED_SIGNAL_THRESHOLD,
    FIXED_STRONG_THRESHOLD,
    FamilyVote,
    _finite,
    _inside_bar_vote,
    _fvg_vote,
    _pb_ema_vote,
    _spearman,
)

SYSTEM_ID = "FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF"
SYSTEM_VERSION = 3
SUPPORTED_BAR_MS = {"1H": 60 * 60 * 1000}
MIN_OVERLAP = 6


def _completed_close_endpoints(candles, *, bar: str):
    width = SUPPORTED_BAR_MS.get(str(bar))
    if width is None:
        return {}, [], None, "unsupported_bar"
    rows = {}
    for candle in candles or []:
        try:
            opened = int(candle.get("ts") or 0)
        except (TypeError, ValueError):
            continue
        close = _finite(candle.get("close"))
        if opened <= 0 or close <= 0:
            continue
        endpoint = opened + width
        if endpoint in rows:
            return {}, [], width, "ambiguous_duplicate_candle_close"
        rows[endpoint] = close
    return rows, sorted(rows), width, None


def oi_vote_causal_asof(candles, open_interest_points, *, bar="1H", lookback=24):
    """Align OI to the latest already-completed price endpoint, never future price."""
    if not open_interest_points:
        return FamilyVote("price_oi_correlation_v3", 0.0, "oi_unavailable", False)

    price_by_end, endpoints, width, error = _completed_close_endpoints(candles, bar=bar)
    if error:
        return FamilyVote("price_oi_correlation_v3", 0.0, error, False)
    if not endpoints or width is None:
        return FamilyVote("price_oi_correlation_v3", 0.0, "price_unavailable", False)

    oi_rows = {}
    for point in open_interest_points or []:
        try:
            ts = int(point.get("ts") or 0)
            oi = float(point.get("value"))
        except (TypeError, ValueError):
            continue
        if ts <= 0 or oi <= 0:
            continue
        if ts in oi_rows:
            return FamilyVote("price_oi_correlation_v3", 0.0, "ambiguous_duplicate_oi_period_end", False)
        oi_rows[ts] = oi

    aligned = []
    used_price_endpoints = set()
    for oi_ts in sorted(oi_rows):
        pos = bisect_right(endpoints, oi_ts) - 1
        if pos < 0:
            continue
        price_ts = endpoints[pos]
        staleness = oi_ts - price_ts
        if staleness < 0 or staleness >= width:
            continue
        # Two OI observations mapped to the same completed price bar are not
        # treated as separate aligned observations.
        if price_ts in used_price_endpoints:
            return FamilyVote("price_oi_correlation_v3", 0.0, "ambiguous_reused_price_endpoint", False)
        used_price_endpoints.add(price_ts)
        aligned.append((oi_ts, price_ts, price_by_end[price_ts], oi_rows[oi_ts], staleness))

    aligned = aligned[-max(MIN_OVERLAP, int(lookback)):]
    if len(aligned) < MIN_OVERLAP:
        return FamilyVote("price_oi_correlation_v3", 0.0, "insufficient_causal_asof_overlap", False)

    prices = [row[2] for row in aligned]
    oi = [row[3] for row in aligned]
    corr = _spearman(prices, oi)
    if corr is None:
        return FamilyVote("price_oi_correlation_v3", 0.0, "correlation_undefined", False)

    price_change = prices[-1] / prices[0] - 1.0
    oi_change = oi[-1] / oi[0] - 1.0
    if abs(price_change) < 0.002 or abs(oi_change) < 0.002:
        return FamilyVote("price_oi_correlation_v3", 0.0, "weak_price_or_oi_change")
    if price_change > 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation_v3", min(1.25, 0.55 + corr * 0.7), "price_and_oi_rising_together")
    if price_change < 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation_v3", -min(1.25, 0.55 + corr * 0.7), "price_falling_while_oi_rises")
    if price_change > 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation_v3", -0.35, "price_rise_with_oi_unwind")
    if price_change < 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation_v3", 0.35, "price_fall_with_oi_unwind")
    return FamilyVote("price_oi_correlation_v3", 0.0, "mixed_price_oi_state")


def score_shadow_signal_v3(candles, open_interest_points=None, *, horizon="24h", bar="1H"):
    votes = [
        _pb_ema_vote(candles),
        _fvg_vote(candles),
        _inside_bar_vote(candles),
        oi_vote_causal_asof(candles, open_interest_points or [], bar=bar),
    ]
    available = [vote for vote in votes if vote.available]
    positive = sum(1 for vote in available if vote.score >= 0.55)
    negative = sum(1 for vote in available if vote.score <= -0.55)
    raw_score = sum(vote.score for vote in available)
    agreement = max(positive, negative)
    direction = "LONG" if raw_score > 0 else "SHORT" if raw_score < 0 else "NEUTRAL"
    threshold = FIXED_STRONG_THRESHOLD if agreement < 3 else FIXED_SIGNAL_THRESHOLD
    action = "WAIT"
    if agreement >= 2 and abs(raw_score) >= threshold:
        action = "SHADOW_BUY" if raw_score > 0 else "SHADOW_SELL"
    return {
        "system": SYSTEM_ID,
        "version": SYSTEM_VERSION,
        "horizon": horizon,
        "bar": bar,
        "direction": direction,
        "action": action,
        "score": round(raw_score, 6),
        "independent_family_agreement": agreement,
        "available_family_count": len(available),
        "families": [vote.__dict__ for vote in votes],
        "timestamp_alignment": "latest_completed_candle_close_at_or_before_oi_period_end",
        "max_price_staleness_ms_exclusive": SUPPORTED_BAR_MS.get(str(bar)),
        "future_price_used": False,
        "nearest_neighbor_used": False,
        "interpolation_used": False,
        "research_only": True,
        "shadow_only": True,
        "trade_authority": False,
        "paper_trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }

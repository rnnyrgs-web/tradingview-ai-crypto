"""Research-only FFriZz V2 open-interest alignment challenger.

This module does not modify FFRIZZ_SECONDARY_V1.  It predeclares a separate
fingerprint whose only change is timestamp semantics for the public Binance
open-interest history: an OI period-END timestamp is matched to the CLOSE
endpoint of the corresponding completed OHLC candle.

No interpolation, nearest-neighbour matching, backfill, production action,
paper action, promotion authority, or broker authority is permitted here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

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

SYSTEM_ID = "FFRIZZ_SECONDARY_V2_OI_CLOSE_END"
SYSTEM_VERSION = 2
SUPPORTED_BAR_MS = {"1H": 60 * 60 * 1000}
MIN_OVERLAP = 6


def _candle_close_index(candles, *, bar: str):
    """Index completed candle closes by their exact close endpoint.

    Candle timestamps in this repository are candle OPEN timestamps in
    milliseconds.  Only explicitly supported fixed-width bars are accepted.
    Duplicate close endpoints are rejected as ambiguous instead of guessed.
    """
    width = SUPPORTED_BAR_MS.get(str(bar))
    if width is None:
        return {}, "unsupported_bar"
    rows = {}
    duplicate = False
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
            duplicate = True
            continue
        rows[endpoint] = close
    if duplicate:
        return {}, "ambiguous_duplicate_candle_close"
    return rows, None


def oi_vote_close_to_period_end(candles, open_interest_points, *, bar="1H", lookback=24):
    """Match completed candle CLOSE endpoints to Binance OI period END exactly."""
    if not open_interest_points:
        return FamilyVote("price_oi_correlation_v2", 0.0, "oi_unavailable", False)

    price_by_end, error = _candle_close_index(candles, bar=bar)
    if error:
        return FamilyVote("price_oi_correlation_v2", 0.0, error, False)

    oi_by_end = {}
    duplicate_oi = False
    for point in open_interest_points or []:
        try:
            ts = int(point.get("ts") or 0)
            oi = float(point.get("value"))
        except (TypeError, ValueError):
            continue
        if ts <= 0 or oi <= 0:
            continue
        if ts in oi_by_end:
            duplicate_oi = True
            continue
        oi_by_end[ts] = oi
    if duplicate_oi:
        return FamilyVote("price_oi_correlation_v2", 0.0, "ambiguous_duplicate_oi_period_end", False)

    shared = sorted(set(price_by_end) & set(oi_by_end))
    shared = shared[-max(MIN_OVERLAP, int(lookback)):]
    if len(shared) < MIN_OVERLAP:
        return FamilyVote("price_oi_correlation_v2", 0.0, "insufficient_close_to_period_end_overlap", False)

    prices = [price_by_end[ts] for ts in shared]
    oi = [oi_by_end[ts] for ts in shared]
    corr = _spearman(prices, oi)
    if corr is None:
        return FamilyVote("price_oi_correlation_v2", 0.0, "correlation_undefined", False)

    price_change = prices[-1] / prices[0] - 1.0
    oi_change = oi[-1] / oi[0] - 1.0
    if abs(price_change) < 0.002 or abs(oi_change) < 0.002:
        return FamilyVote("price_oi_correlation_v2", 0.0, "weak_price_or_oi_change")
    if price_change > 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation_v2", min(1.25, 0.55 + corr * 0.7), "price_and_oi_rising_together")
    if price_change < 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation_v2", -min(1.25, 0.55 + corr * 0.7), "price_falling_while_oi_rises")
    if price_change > 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation_v2", -0.35, "price_rise_with_oi_unwind")
    if price_change < 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation_v2", 0.35, "price_fall_with_oi_unwind")
    return FamilyVote("price_oi_correlation_v2", 0.0, "mixed_price_oi_state")


def score_shadow_signal_v2(candles, open_interest_points=None, *, horizon="24h", bar="1H"):
    """Score the predeclared V2 challenger without changing V1 thresholds."""
    votes = [
        _pb_ema_vote(candles),
        _fvg_vote(candles),
        _inside_bar_vote(candles),
        oi_vote_close_to_period_end(candles, open_interest_points or [], bar=bar),
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
        "timestamp_alignment": "completed_candle_close_exactly_equals_oi_period_end",
        "interpolation_used": False,
        "backfill_used": False,
        "research_only": True,
        "shadow_only": True,
        "trade_authority": False,
        "paper_trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }


def feature_availability_diagnostics(signals_by_horizon):
    """Bounded count-only diagnostics; exposes no symbols or raw ledger rows."""
    output = {}
    for horizon, signals in (signals_by_horizon or {}).items():
        counts = Counter()
        scored = 0
        for signal in signals or []:
            scored += 1
            for family in signal.get("families") or []:
                name = str(family.get("family") or "unknown")
                if family.get("available") is False:
                    counts[f"{name}:unavailable"] += 1
                else:
                    counts[f"{name}:available"] += 1
        output[str(horizon)] = {
            "signals_scored": scored,
            "family_counts": dict(sorted(counts.items())),
        }
    return {
        "system": SYSTEM_ID,
        "diagnostic_only": True,
        "symbol_level_data_exposed": False,
        "horizons": output,
        "trade_authority": False,
        "promotion_authority": False,
    }

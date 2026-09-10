"""Research-only FFriZz-inspired secondary crypto signal engine.

This module implements public concepts described in TradingView scripts authored
by the exact account `FFriZz` without copying protected Pine source. It is a
separate shadow/research signal family and has zero production, paper, broker,
or promotion authority.

Predeclared concept families:
- PlayBit EMA: 200-EMA high/close channel and trend location.
- Fair Value Gaps (FVG): three-candle imbalance, mitigation and proximity.
- Inside-bar compression/breakout context.
- Price/Open-Interest correlation using timestamp-aligned public OI history.

The objective is not to assume these indicators are predictive. Their fixed,
timestamp-safe features are intended to be backtested, diagnosed and learned
from under the repository's existing chronological/OOS/multiple-testing gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean


HORIZON_PROFILES = {
    "6h": {"bar": "1H", "forward_bars": 6},
    "12h": {"bar": "1H", "forward_bars": 12},
    "24h": {"bar": "1H", "forward_bars": 24},
    "48h": {"bar": "4H", "forward_bars": 12},
    "72h": {"bar": "4H", "forward_bars": 18},
    "7d": {"bar": "4H", "forward_bars": 42},
}
HORIZON_ORDER = ("6h", "12h", "24h", "48h", "72h", "7d")
EMA_LENGTH = 200
MIN_CANDLES = EMA_LENGTH + 12
FIXED_SIGNAL_THRESHOLD = 2.25
FIXED_STRONG_THRESHOLD = 3.25
FIXED_ROUND_TRIP_COST_BPS = 12.0


@dataclass(frozen=True)
class FamilyVote:
    family: str
    score: float
    reason: str
    available: bool = True


def _finite(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _ema(values, length=EMA_LENGTH):
    values = [_finite(v) for v in values]
    if len(values) < length:
        return None
    alpha = 2.0 / (length + 1.0)
    current = mean(values[:length])
    for value in values[length:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def _rank(values):
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _pearson(x, y):
    if len(x) != len(y) or len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    denom = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denom <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def _spearman(x, y):
    if len(x) != len(y) or len(x) < 5:
        return None
    return _pearson(_rank(x), _rank(y))


def _pb_ema_vote(candles):
    if len(candles) < EMA_LENGTH:
        return FamilyVote("pb_ema", 0.0, "insufficient_history", False)
    highs = [_finite(c.get("high")) for c in candles]
    closes = [_finite(c.get("close")) for c in candles]
    ema_high = _ema(highs)
    ema_close = _ema(closes)
    last = closes[-1]
    if not ema_high or not ema_close or last <= 0:
        return FamilyVote("pb_ema", 0.0, "invalid_ema_state", False)
    upper = max(ema_high, ema_close)
    lower = min(ema_high, ema_close)
    width_pct = max((upper - lower) / last * 100.0, 0.02)
    if last > upper:
        distance = min(2.0, (last - upper) / last * 100.0 / width_pct)
        return FamilyVote("pb_ema", 1.0 + 0.35 * distance, "close_above_200_ema_channel")
    if last < lower:
        distance = min(2.0, (lower - last) / last * 100.0 / width_pct)
        return FamilyVote("pb_ema", -(1.0 + 0.35 * distance), "close_below_200_ema_channel")
    midpoint = (upper + lower) / 2.0
    score = 0.30 if last >= midpoint else -0.30
    return FamilyVote("pb_ema", score, "close_inside_200_ema_channel")


def _latest_unmitigated_fvg(candles):
    latest = None
    for i in range(2, len(candles)):
        left = candles[i - 2]
        current = candles[i]
        left_high = _finite(left.get("high"))
        left_low = _finite(left.get("low"))
        current_high = _finite(current.get("high"))
        current_low = _finite(current.get("low"))
        if current_low > left_high > 0:
            latest = {"direction": "LONG", "low": left_high, "high": current_low, "created_index": i}
        elif current_high < left_low and current_high > 0:
            latest = {"direction": "SHORT", "low": current_high, "high": left_low, "created_index": i}
    if latest is None:
        return None
    for candle in candles[latest["created_index"] + 1:]:
        low = _finite(candle.get("low"))
        high = _finite(candle.get("high"))
        if latest["direction"] == "LONG" and low <= latest["low"]:
            latest["mitigated"] = True
            return latest
        if latest["direction"] == "SHORT" and high >= latest["high"]:
            latest["mitigated"] = True
            return latest
    latest["mitigated"] = False
    return latest


def _fvg_vote(candles):
    fvg = _latest_unmitigated_fvg(candles)
    if not fvg:
        return FamilyVote("fvg", 0.0, "no_recent_fvg")
    last = _finite(candles[-1].get("close"))
    if last <= 0:
        return FamilyVote("fvg", 0.0, "invalid_close", False)
    if fvg.get("mitigated"):
        return FamilyVote("fvg", 0.0, "latest_fvg_mitigated")
    midpoint = (fvg["low"] + fvg["high"]) / 2.0
    distance_pct = abs(last - midpoint) / last * 100.0
    proximity = max(0.25, 1.0 - min(distance_pct, 5.0) / 5.0)
    sign = 1.0 if fvg["direction"] == "LONG" else -1.0
    return FamilyVote("fvg", sign * (0.70 + 0.55 * proximity), f"unmitigated_{fvg['direction'].lower()}_fvg")


def _inside_bar_vote(candles):
    if len(candles) < 3:
        return FamilyVote("inside_bar", 0.0, "insufficient_history", False)
    mother = candles[-3]
    inside = candles[-2]
    latest = candles[-1]
    mh, ml = _finite(mother.get("high")), _finite(mother.get("low"))
    ih, il = _finite(inside.get("high")), _finite(inside.get("low"))
    close = _finite(latest.get("close"))
    if not (mh > ml > 0 and ih <= mh and il >= ml):
        return FamilyVote("inside_bar", 0.0, "no_inside_bar_breakout")
    if close > mh:
        return FamilyVote("inside_bar", 1.0, "inside_bar_upside_breakout")
    if close < ml:
        return FamilyVote("inside_bar", -1.0, "inside_bar_downside_breakout")
    return FamilyVote("inside_bar", 0.0, "inside_bar_compression_unresolved")


def _oi_vote(candles, open_interest_points, lookback=24):
    if not open_interest_points:
        return FamilyVote("price_oi_correlation", 0.0, "oi_unavailable", False)
    price_by_ts = {int(c.get("ts") or 0): _finite(c.get("close")) for c in candles}
    aligned = []
    for point in open_interest_points:
        try:
            ts = int(point.get("ts") or 0)
            oi = float(point.get("value"))
        except (TypeError, ValueError):
            continue
        price = price_by_ts.get(ts)
        if ts > 0 and price and oi > 0:
            aligned.append((ts, price, oi))
    aligned = aligned[-max(6, int(lookback)):]
    if len(aligned) < 6:
        return FamilyVote("price_oi_correlation", 0.0, "insufficient_exact_timestamp_overlap", False)
    prices = [row[1] for row in aligned]
    oi = [row[2] for row in aligned]
    corr = _spearman(prices, oi)
    if corr is None:
        return FamilyVote("price_oi_correlation", 0.0, "correlation_undefined", False)
    price_change = prices[-1] / prices[0] - 1.0
    oi_change = oi[-1] / oi[0] - 1.0
    if abs(price_change) < 0.002 or abs(oi_change) < 0.002:
        return FamilyVote("price_oi_correlation", 0.0, "weak_price_or_oi_change")
    if price_change > 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation", min(1.25, 0.55 + corr * 0.7), "price_and_oi_rising_together")
    if price_change < 0 and oi_change > 0 and corr > 0.25:
        return FamilyVote("price_oi_correlation", -min(1.25, 0.55 + corr * 0.7), "price_falling_while_oi_rises")
    if price_change > 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation", -0.35, "price_rise_with_oi_unwind")
    if price_change < 0 and oi_change < 0:
        return FamilyVote("price_oi_correlation", 0.35, "price_fall_with_oi_unwind")
    return FamilyVote("price_oi_correlation", 0.0, "mixed_price_oi_state")


def feature_votes(candles, open_interest_points=None):
    candles = list(candles or [])
    if len(candles) < MIN_CANDLES:
        return [
            FamilyVote("pb_ema", 0.0, "insufficient_history", False),
            FamilyVote("fvg", 0.0, "insufficient_history", False),
            FamilyVote("inside_bar", 0.0, "insufficient_history", False),
            FamilyVote("price_oi_correlation", 0.0, "insufficient_history", False),
        ]
    return [
        _pb_ema_vote(candles),
        _fvg_vote(candles),
        _inside_bar_vote(candles),
        _oi_vote(candles, open_interest_points or []),
    ]


def score_shadow_signal(candles, open_interest_points=None, *, horizon="24h"):
    if horizon not in HORIZON_PROFILES:
        raise ValueError(f"unsupported horizon: {horizon}")
    votes = feature_votes(candles, open_interest_points)
    available = [vote for vote in votes if vote.available]
    positive = sum(1 for vote in available if vote.score >= 0.55)
    negative = sum(1 for vote in available if vote.score <= -0.55)
    raw_score = sum(vote.score for vote in available)
    independent_agreement = max(positive, negative)
    direction = "LONG" if raw_score > 0 else "SHORT" if raw_score < 0 else "NEUTRAL"
    threshold = FIXED_STRONG_THRESHOLD if independent_agreement < 3 else FIXED_SIGNAL_THRESHOLD
    action = "WAIT"
    if independent_agreement >= 2 and abs(raw_score) >= threshold:
        action = "SHADOW_BUY" if raw_score > 0 else "SHADOW_SELL"
    return {
        "system": "FFRIZZ_SECONDARY_V1",
        "horizon": horizon,
        "bar": HORIZON_PROFILES[horizon]["bar"],
        "direction": direction,
        "action": action,
        "score": round(raw_score, 6),
        "independent_family_agreement": independent_agreement,
        "available_family_count": len(available),
        "families": [vote.__dict__ for vote in votes],
        "research_only": True,
        "shadow_only": True,
        "trade_authority": False,
        "paper_trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }


def chronological_backtest(candles, *, horizon="24h", cost_bps=FIXED_ROUND_TRIP_COST_BPS):
    """Fixed-rule, non-overlapping diagnostic backtest; never promotion evidence alone."""
    if horizon not in HORIZON_PROFILES:
        raise ValueError(f"unsupported horizon: {horizon}")
    candles = list(candles or [])
    forward = int(HORIZON_PROFILES[horizon]["forward_bars"])
    rows = []
    start = max(MIN_CANDLES, EMA_LENGTH + 12)
    for i in range(start, len(candles) - forward, forward):
        history = candles[: i + 1]
        signal = score_shadow_signal(history, [], horizon=horizon)
        if signal["action"] == "WAIT":
            continue
        entry = _finite(candles[i].get("close"))
        exit_price = _finite(candles[i + forward].get("close"))
        if entry <= 0 or exit_price <= 0:
            continue
        gross = (exit_price / entry - 1.0) * 100.0
        signed = gross if signal["direction"] == "LONG" else -gross
        net = signed - float(cost_bps) / 100.0
        rows.append({"index": i, "direction": signal["direction"], "gross_pct": signed, "net_pct": net, "correct": net > 0})
    wins = sum(1 for row in rows if row["correct"])
    total = len(rows)
    return {
        "system": "FFRIZZ_SECONDARY_V1",
        "horizon": horizon,
        "research_only": True,
        "non_overlapping": True,
        "fixed_rules": True,
        "round_trip_cost_bps": float(cost_bps),
        "signals": total,
        "accuracy": (wins / total) if total else None,
        "mean_net_pct": mean([row["net_pct"] for row in rows]) if rows else None,
        "rows": rows,
        "warning": "Diagnostic only. Requires canonical chronological development/validation/untouched-OOS, robustness, multiple-testing and genuine-forward proof before any production consideration.",
        "trade_authority": False,
        "promotion_authority": False,
    }

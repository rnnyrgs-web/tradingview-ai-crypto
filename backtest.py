from features import timeframe_features
from market_data import get_history
from utils import mean
from config import BACKTEST_COST_BPS


def directional_return(entry, future, direction):
    raw = (future / entry - 1.0) * 100.0
    return raw if direction == "LONG" else -raw


def max_drawdown_pct(returns):
    equity = 100.0
    peak = equity
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + r / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def execution_cost_scenarios(base_cost_bps=BACKTEST_COST_BPS):
    """Deterministic conservative cost stress grid.

    Historical candle data does not contain executable bid/ask history, so the
    backtester must not invent a historical spread. Instead we stress every
    strategy under progressively worse round-trip cost assumptions. A strategy
    that only survives the configured base cost is visibly fragile and remains
    research evidence, never promotion evidence by itself.
    """
    base = max(float(base_cost_bps), 0.0)
    return tuple(dict.fromkeys(round(base * multiplier, 4) for multiplier in (1.0, 1.5, 2.0, 3.0)))


def _validate_timestamps(hist):
    """Require ordered candle timestamps before using positional future bars.

    Cost stress intentionally reuses the exact same trade path. If timestamps
    are missing or out of order, ``i + 1`` is not defensibly the next bar and
    applying execution costs would create misleading evidence. Refuse the
    backtest rather than sorting/filling unavailable historical data.
    """
    previous = None
    for row in hist:
        try:
            timestamp = int(row["ts"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Timestamp data unavailable; execution-cost stress refused") from None
        if previous is not None and timestamp <= previous:
            raise ValueError("Candle timestamps are not strictly increasing; backtest refused")
        previous = timestamp


def summarize_returns(returns):
    wins = [x for x in returns if x > 0]
    losses = [x for x in returns if x <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(returns),
        "win_rate_pct": round(len(wins) / len(returns) * 100, 2) if returns else 0,
        "avg_trade_pct": round(mean(returns), 4),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        "sum_net_returns_pct": round(sum(returns), 3),
        "max_drawdown_pct": round(max_drawdown_pct(returns), 3),
    }


def _features_at(hist, i):
    # All current features use at most ~100 candles. Keeping a small rolling
    # context prevents deep cloud backtests from becoming O(n^2).
    return timeframe_features(hist[max(0, i - 140):i + 1])


def _score_history(hist, bar, threshold, cost_bps=BACKTEST_COST_BPS):
    _validate_timestamps(hist)
    max_hold = {"15m": 16, "1H": 24, "4H": 42, "1D": 30}.get(bar, 16)
    rs = []
    i = 100
    round_trip_cost_pct = max(float(cost_bps), 0.0) / 100.0

    while i < len(hist) - max_hold - 2:
        ft = _features_at(hist, i)
        if not ft or abs(ft["score"]) < threshold or ft["atr"] <= 0:
            i += 1
            continue

        direction = "LONG" if ft["score"] > 0 else "SHORT"
        # Entry remains next-bar open so the decision uses only information
        # available through candle i. No current/future bar close is used.
        entry = hist[i + 1]["open"]
        risk = max(ft["atr"] * 1.55, entry * 0.0035)
        target = entry + risk * 1.9 if direction == "LONG" else entry - risk * 1.9
        stop = entry - risk if direction == "LONG" else entry + risk
        exit_price = hist[min(i + 1 + max_hold, len(hist) - 1)]["close"]

        for j in range(i + 1, min(i + 1 + max_hold, len(hist))):
            b = hist[j]
            hs = b["low"] <= stop if direction == "LONG" else b["high"] >= stop
            ht = b["high"] >= target if direction == "LONG" else b["low"] <= target
            # Conservative same-candle assumption: stop wins the ambiguity.
            if hs:
                exit_price = stop
                break
            if ht:
                exit_price = target
                break

        rs.append(directional_return(entry, exit_price, direction) - round_trip_cost_pct)
        i += max_hold

    return rs


def run_backtest(symbol, bar="15m", bars=2500, threshold=2.25):
    hist = get_history(symbol, bar, bars)
    if len(hist) < 300:
        raise RuntimeError("Not enough historical candles")

    trades = _score_history(hist, bar, threshold, BACKTEST_COST_BPS)
    summary = summarize_returns(trades)
    stress = {}
    for cost_bps in execution_cost_scenarios():
        stressed = _score_history(hist, bar, threshold, cost_bps)
        stress[str(cost_bps)] = {"cost_bps_round_trip": cost_bps, **summarize_returns(stressed)}

    return {
        "ok": True,
        "symbol": symbol,
        "bar": bar,
        "candles": len(hist),
        "threshold": threshold,
        **summary,
        "cost_bps_round_trip": BACKTEST_COST_BPS,
        "execution_cost_stress": stress,
        "execution_cost_note": (
            "Candle history lacks executable historical bid/ask quotes; no spread is fabricated. "
            "Results are stress-tested under deterministic higher round-trip costs instead. "
            "Missing or non-chronological candle timestamps fail closed."
        ),
        "warning": "Research backtest only. Use walk-forward/holdout results before trusting live signals."
    }


def walk_forward(symbol, bar="15m", bars=3000):
    hist = get_history(symbol, bar, bars)
    if len(hist) < 1000:
        raise RuntimeError("Need at least 1000 candles for walk-forward")

    _validate_timestamps(hist)
    n = len(hist)
    train = hist[:int(n * 0.6)]
    valid = hist[int(n * 0.6):int(n * 0.8)]
    test = hist[int(n * 0.8):]

    def score_segment(seg, threshold, cost_bps=BACKTEST_COST_BPS):
        if len(seg) < 300:
            return {"trades": 0, "avg": 0.0, "sum": 0.0, "max_drawdown_pct": 0.0}
        rs = _score_history(seg, bar, threshold, cost_bps)
        return {
            "trades": len(rs),
            "avg": mean(rs),
            "sum": sum(rs),
            "max_drawdown_pct": max_drawdown_pct(rs),
        }

    thresholds = [1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
    train_scores = {t: score_segment(train, t) for t in thresholds}
    viable = [t for t, v in train_scores.items() if v["trades"] >= 10]
    if not viable:
        return {"ok": True, "symbol": symbol, "bar": bar, "message": "No viable training threshold"}

    best = max(viable, key=lambda t: train_scores[t]["avg"])
    valid_score = score_segment(valid, best)
    test_score = score_segment(test, best)
    holdout_cost_stress = {
        str(cost_bps): {
            "cost_bps_round_trip": cost_bps,
            **score_segment(test, best, cost_bps),
        }
        for cost_bps in execution_cost_scenarios()
    }

    return {
        "ok": True,
        "symbol": symbol,
        "bar": bar,
        "candles": len(hist),
        "selected_threshold": best,
        "train": train_scores[best],
        "validation": valid_score,
        "holdout_test": test_score,
        "holdout_execution_cost_stress": holdout_cost_stress,
        "note": (
            "Threshold selected on training only; holdout remains untouched until final scoring. "
            "Cost stress changes only the assumed round-trip execution cost, not trade selection. "
            "Missing or non-chronological candle timestamps fail closed."
        )
    }

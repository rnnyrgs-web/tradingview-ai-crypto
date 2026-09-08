from math import isfinite

from features import atr, ema, rsi, slope_pct, zscore_last
from market_data import get_history
from config import BACKTEST_COST_BPS
from robustness import evaluate_robustness


STRATEGY_FAMILIES = (
    "trend",
    "breakout",
    "momentum",
    "mean_reversion",
    "volatility_expansion",
    "relative_strength",
)


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _profit_factor(returns):
    gains = sum(x for x in returns if x > 0)
    losses = abs(sum(x for x in returns if x <= 0))
    if losses == 0:
        return None if gains <= 0 else 999.0
    return gains / losses


def _max_drawdown_pct(returns):
    equity = 100.0
    peak = equity
    max_dd = 0.0
    for ret in returns:
        equity *= 1.0 + ret / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def _segment_metrics(returns):
    wins = sum(1 for x in returns if x > 0)
    pf = _profit_factor(returns)
    return {
        "trades": len(returns),
        "win_rate_pct": round(wins / len(returns) * 100.0, 2) if returns else 0.0,
        "avg_trade_pct": round(_mean(returns), 5),
        "sum_net_returns_pct": round(sum(returns), 4),
        "profit_factor": round(pf, 3) if pf is not None and isfinite(pf) else pf,
        "max_drawdown_pct": round(_max_drawdown_pct(returns), 3),
    }


def _true_range(candles, i):
    if i <= 0:
        return candles[i]["high"] - candles[i]["low"]
    prev_close = candles[i - 1]["close"]
    return max(
        candles[i]["high"] - candles[i]["low"],
        abs(candles[i]["high"] - prev_close),
        abs(candles[i]["low"] - prev_close),
    )


def _signal_trend(candles, i, _benchmark, scale=1.0):
    if i < 60:
        return None
    closes = [x["close"] for x in candles[i - 59:i + 1]]
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    slope = slope_pct(closes, 12)
    if closes[-1] > e20 > e50 and slope > 0.04 * scale:
        return "LONG"
    if closes[-1] < e20 < e50 and slope < -0.04 * scale:
        return "SHORT"
    return None


def _signal_breakout(candles, i, _benchmark, scale=1.0):
    if i < 35:
        return None
    prior = candles[i - 20:i]
    close = candles[i]["close"]
    vols = [x["volume"] for x in candles[i - 29:i + 1]]
    vol_z = zscore_last(vols, 30)
    if close > max(x["high"] for x in prior) and vol_z > 0.35 * scale:
        return "LONG"
    if close < min(x["low"] for x in prior) and vol_z > 0.35 * scale:
        return "SHORT"
    return None


def _signal_momentum(candles, i, _benchmark, scale=1.0):
    if i < 35:
        return None
    closes = [x["close"] for x in candles[i - 34:i + 1]]
    rrsi = rsi(closes, 14)
    a = atr(candles[max(0, i - 30):i + 1], 14)
    move = closes[-1] - closes[-7]
    normalized = move / max(a, closes[-1] * 0.001)
    rsi_edge = 58 + 8 * (scale - 1.0)
    if rrsi >= rsi_edge and normalized >= 1.1 * scale:
        return "LONG"
    if rrsi <= 100 - rsi_edge and normalized <= -1.1 * scale:
        return "SHORT"
    return None


def _signal_mean_reversion(candles, i, _benchmark, scale=1.0):
    if i < 40:
        return None
    window = candles[i - 39:i + 1]
    closes = [x["close"] for x in window]
    e20 = ema(closes, 20)
    a = atr(window, 14)
    rrsi = rsi(closes, 14)
    last = closes[-1]
    if a <= 0:
        return None
    rsi_edge = 35 - 10 * (scale - 1.0)
    if last < e20 - 1.25 * scale * a and rrsi <= rsi_edge:
        return "LONG"
    if last > e20 + 1.25 * scale * a and rrsi >= 100 - rsi_edge:
        return "SHORT"
    return None


def _signal_volatility_expansion(candles, i, _benchmark, scale=1.0):
    if i < 35:
        return None
    prior_tr = [_true_range(candles, j) for j in range(i - 20, i)]
    current_tr = _true_range(candles, i)
    baseline = _mean(prior_tr)
    if baseline <= 0 or current_tr < 1.55 * scale * baseline:
        return None
    bar = candles[i]
    span = max(bar["high"] - bar["low"], bar["close"] * 0.0005)
    location = (bar["close"] - bar["low"]) / span
    vols = [x["volume"] for x in candles[i - 29:i + 1]]
    if zscore_last(vols, 30) < 0.45 * scale:
        return None
    if location >= 0.72 and bar["close"] > bar["open"]:
        return "LONG"
    if location <= 0.28 and bar["close"] < bar["open"]:
        return "SHORT"
    return None


def _signal_relative_strength(candles, i, benchmark, scale=1.0):
    if i < 30 or not benchmark:
        return None
    now_ts = candles[i]["ts"]
    past_ts = candles[i - 20]["ts"]
    b_now = benchmark.get(now_ts)
    b_past = benchmark.get(past_ts)
    if not b_now or not b_past or b_past <= 0:
        return None
    asset_now = candles[i]["close"]
    asset_past = candles[i - 20]["close"]
    if asset_past <= 0:
        return None
    asset_ret = asset_now / asset_past - 1.0
    bench_ret = b_now / b_past - 1.0
    excess = asset_ret - bench_ret
    local_slope = slope_pct([x["close"] for x in candles[i - 19:i + 1]], 12)
    if excess >= 0.025 * scale and local_slope > 0:
        return "LONG"
    if excess <= -0.025 * scale and local_slope < 0:
        return "SHORT"
    return None


SIGNAL_FUNCTIONS = {
    "trend": _signal_trend,
    "breakout": _signal_breakout,
    "momentum": _signal_momentum,
    "mean_reversion": _signal_mean_reversion,
    "volatility_expansion": _signal_volatility_expansion,
    "relative_strength": _signal_relative_strength,
}


def _regime(candles, i):
    context = candles[max(0, i - 59):i + 1]
    closes = [row["close"] for row in context]
    last = closes[-1]
    a = atr(context, 14)
    gap = abs(ema(closes, 20) / ema(closes, 50) - 1.0) if len(closes) >= 50 else 0.0
    if gap >= 0.012:
        return "TREND"
    if a / last >= 0.018:
        return "HIGH_VOL"
    return "RANGE"


def _simulate(candles, bar, family, benchmark=None, parameter_scale=1.0, detailed=False):
    signal_fn = SIGNAL_FUNCTIONS[family]
    max_hold = {"15m": 16, "1H": 24, "4H": 42, "1D": 30}.get(bar, 16)
    benchmark = benchmark or {}
    returns = []
    i = 70

    while i < len(candles) - max_hold - 2:
        direction = signal_fn(candles, i, benchmark, parameter_scale)
        if not direction:
            i += 1
            continue

        context = candles[max(0, i - 40):i + 1]
        a = atr(context, 14)
        entry = candles[i + 1]["open"]
        if a <= 0 or entry <= 0:
            i += 1
            continue

        risk = max(a * 1.55, entry * 0.0035)
        target = entry + risk * 1.9 if direction == "LONG" else entry - risk * 1.9
        stop = entry - risk if direction == "LONG" else entry + risk
        exit_price = candles[min(i + 1 + max_hold, len(candles) - 1)]["close"]

        for j in range(i + 1, min(i + 1 + max_hold, len(candles))):
            bar_data = candles[j]
            stop_hit = bar_data["low"] <= stop if direction == "LONG" else bar_data["high"] >= stop
            target_hit = bar_data["high"] >= target if direction == "LONG" else bar_data["low"] <= target
            if stop_hit:
                exit_price = stop
                break
            if target_hit:
                exit_price = target
                break

        raw = (exit_price / entry - 1.0) * 100.0
        directional = raw if direction == "LONG" else -raw
        result = directional - BACKTEST_COST_BPS / 100.0
        returns.append({"return_pct": result, "regime": _regime(candles, i)}) if detailed else returns.append(result)
        i += max_hold

    return returns


def _quality_gate(train, validation, holdout):
    reasons = []
    oos_trades = validation["trades"] + holdout["trades"]
    val_pf = validation["profit_factor"] or 0.0
    test_pf = holdout["profit_factor"] or 0.0

    if train["trades"] < 12:
        reasons.append("train_trades<12")
    if validation["trades"] < 6:
        reasons.append("validation_trades<6")
    if holdout["trades"] < 6:
        reasons.append("holdout_trades<6")
    if oos_trades < 15:
        reasons.append("oos_trades<15")
    if validation["avg_trade_pct"] <= 0:
        reasons.append("validation_expectancy<=0")
    if holdout["avg_trade_pct"] <= 0:
        reasons.append("holdout_expectancy<=0")
    if val_pf < 1.05:
        reasons.append("validation_pf<1.05")
    if test_pf < 1.10:
        reasons.append("holdout_pf<1.10")
    if validation["max_drawdown_pct"] > 18:
        reasons.append("validation_drawdown>18")
    if holdout["max_drawdown_pct"] > 18:
        reasons.append("holdout_drawdown>18")

    return {
        "passed": not reasons,
        "eligible_for_live_ensemble": not reasons,
        "reasons": reasons,
        "policy": {
            "min_train_trades": 12,
            "min_validation_trades": 6,
            "min_holdout_trades": 6,
            "min_combined_oos_trades": 15,
            "validation_avg_trade_gt": 0.0,
            "holdout_avg_trade_gt": 0.0,
            "validation_profit_factor_gte": 1.05,
            "holdout_profit_factor_gte": 1.10,
            "max_validation_drawdown_pct": 18.0,
            "max_holdout_drawdown_pct": 18.0,
        },
    }


def _skipped_robustness(gate):
    """Fail fast before expensive robustness when basic OOS quality already fails.

    This cannot promote a strategy or weaken a gate: a quality-gate failure is
    already ineligible. Skipping bootstrap/perturbation work only saves compute
    for candidates that are deterministically RESEARCH_ONLY.
    """
    return {
        "passed": False,
        "status": "SKIPPED_QUALITY_GATE_FAILED",
        "reason": "quality_gate_failed_before_expensive_robustness",
        "gate_reasons": list(gate.get("reasons") or []),
        "bootstrap_runs": 0,
    }


def evaluate_strategy_registry(symbol, bar="15m", bars=5000):
    history = get_history(symbol, bar, bars)
    if len(history) < 1000:
        raise RuntimeError("Need at least 1000 candles for strategy-family research")

    benchmark_history = history if symbol == "BTC-USDT" else get_history("BTC-USDT", bar, bars)
    benchmark = {x["ts"]: x["close"] for x in benchmark_history}

    n = len(history)
    train = history[:int(n * 0.6)]
    validation = history[int(n * 0.6):int(n * 0.8)]
    holdout = history[int(n * 0.8):]

    registry = []
    for family in STRATEGY_FAMILIES:
        train_returns = _simulate(train, bar, family, benchmark)
        validation_returns = _simulate(validation, bar, family, benchmark)
        holdout_records = _simulate(holdout, bar, family, benchmark, detailed=True)
        holdout_returns = [row["return_pct"] for row in holdout_records]
        train_metrics = _segment_metrics(train_returns)
        validation_metrics = _segment_metrics(validation_returns)
        holdout_metrics = _segment_metrics(holdout_returns)
        gate = _quality_gate(train_metrics, validation_metrics, holdout_metrics)
        if gate["passed"]:
            robustness = evaluate_robustness(
                validation_returns + holdout_returns,
                {
                    "threshold_90pct": _simulate(holdout, bar, family, benchmark, parameter_scale=0.9),
                    "threshold_110pct": _simulate(holdout, bar, family, benchmark, parameter_scale=1.1),
                },
                {
                    regime: [row["return_pct"] for row in holdout_records if row["regime"] == regime]
                    for regime in ("TREND", "HIGH_VOL", "RANGE")
                },
                f"{symbol}|{bar}|{family}",
            )
        else:
            robustness = _skipped_robustness(gate)
        eligible = gate["passed"] and robustness["passed"]
        registry.append({
            "strategy_family": family,
            "status": "ROBUST_OOS" if eligible else "RESEARCH_ONLY",
            "train": train_metrics,
            "validation": validation_metrics,
            "holdout_test": holdout_metrics,
            "quality_gate": gate,
            "robustness": robustness,
            "eligible_for_promotion_review": eligible,
        })

    return {
        "ok": True,
        "symbol": symbol,
        "bar": bar,
        "candles": len(history),
        "benchmark": "BTC-USDT",
        "cost_bps_round_trip": BACKTEST_COST_BPS,
        "families_tested": len(registry),
        "eligible_count": sum(1 for x in registry if x["quality_gate"]["passed"]),
        "registry": registry,
        "note": "No strategy may influence the live ensemble unless its OOS quality gate passes. Passing is necessary, not a profit guarantee.",
    }

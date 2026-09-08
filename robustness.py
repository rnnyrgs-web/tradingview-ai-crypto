"""Deterministic OOS robustness tests; never a standalone live approval."""

from __future__ import annotations

import hashlib
import math


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _valid_returns(values):
    if not isinstance(values, (list, tuple)):
        return False
    return all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values)


def _drawdown(returns):
    equity = peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak if peak else 1.0)
    return worst * 100.0


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))]


def monte_carlo_bootstrap(returns, identity_seed, simulations=500):
    if not _valid_returns(returns):
        return {"passed": False, "reason": "invalid_nonfinite_oos_returns", "simulations": 0}
    if len(returns) < 12:
        return {"passed": False, "reason": "oos_trades<12", "simulations": 0}
    if not isinstance(simulations, int) or simulations < 100 or simulations > 5000:
        return {"passed": False, "reason": "invalid_simulation_count", "simulations": 0}
    totals, drawdowns = [], []
    seed = str(identity_seed).encode("utf-8")
    counter = 0
    for _ in range(simulations):
        sample = []
        for _ in returns:
            block = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
            sample.append(returns[int.from_bytes(block[:8], "big") % len(returns)])
            counter += 1
        totals.append(sum(sample))
        drawdowns.append(_drawdown(sample))
    probability_positive = sum(value > 0 for value in totals) / simulations
    p05_total = _percentile(totals, 0.05)
    p95_drawdown = _percentile(drawdowns, 0.95)
    passed = probability_positive >= 0.80 and p05_total > 0 and p95_drawdown <= 25.0
    return {
        "passed": passed,
        "simulations": simulations,
        "probability_positive": round(probability_positive, 4),
        "p05_sum_returns_pct": round(p05_total, 4),
        "p95_max_drawdown_pct": round(p95_drawdown, 4),
        "policy": {"probability_positive_gte": 0.80, "p05_sum_returns_gt": 0.0, "p95_drawdown_lte": 25.0},
    }


def evaluate_robustness(base_oos, parameter_variants, regime_returns, identity_seed):
    malformed = []
    if not _valid_returns(base_oos):
        malformed.append("base_oos")
    if not isinstance(parameter_variants, dict) or not parameter_variants:
        malformed.append("parameter_variants")
    else:
        malformed.extend(
            f"parameter:{name}" for name, values in parameter_variants.items()
            if not _valid_returns(values)
        )
    if not isinstance(regime_returns, dict) or not regime_returns:
        malformed.append("regime_returns")
    else:
        malformed.extend(
            f"regime:{name}" for name, values in regime_returns.items()
            if not _valid_returns(values)
        )
    if malformed:
        return {
            "passed": False,
            "reason": "malformed_or_nonfinite_robustness_input",
            "invalid_inputs": malformed,
            "monte_carlo": {"passed": False, "simulations": 0},
            "parameter_stability": {"passed": False, "variants": {}},
            "regime_stability": {"passed": False, "regimes": {}},
            "policy": "Malformed, non-finite or missing robustness inputs fail closed.",
        }

    monte_carlo = monte_carlo_bootstrap(base_oos, identity_seed)
    parameter_metrics = {
        name: {"trades": len(values), "avg_trade_pct": round(_mean(values), 6)}
        for name, values in parameter_variants.items()
    }
    parameter_passed = bool(parameter_metrics) and all(
        metric["trades"] >= 6 and metric["avg_trade_pct"] > 0
        for metric in parameter_metrics.values()
    )
    qualifying_regimes = {
        name: values for name, values in regime_returns.items() if len(values) >= 3
    }
    regime_metrics = {
        name: {"trades": len(values), "avg_trade_pct": round(_mean(values), 6)}
        for name, values in qualifying_regimes.items()
    }
    regime_passed = len(regime_metrics) >= 2 and all(
        metric["avg_trade_pct"] > 0 for metric in regime_metrics.values()
    )
    passed = monte_carlo["passed"] and parameter_passed and regime_passed
    return {
        "passed": passed,
        "monte_carlo": monte_carlo,
        "parameter_stability": {"passed": parameter_passed, "variants": parameter_metrics},
        "regime_stability": {"passed": regime_passed, "regimes": regime_metrics},
        "policy": "All Monte Carlo, parameter-perturbation and multi-regime checks must pass.",
    }

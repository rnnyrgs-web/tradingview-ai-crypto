"""Research-only economic calibration over independent resolved forecasts.

The goal is to estimate whether a signal's probability-weighted payoff is
positive after conservative execution costs. This module never mutates
production, opens untouched OOS, or grants trade/promotion authority.
"""

from __future__ import annotations

from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

DEFAULT_ROUND_TRIP_COST_PCT = 0.12
COST_STRESS_MULTIPLIERS = (1.0, 1.5, 2.0, 3.0)
CONFIDENCE_BANDS = ((0.0, 60.0, "<60"), (60.0, 70.0, "60-69"), (70.0, 80.0, "70-79"), (80.0, 90.0, "80-89"), (90.0, 101.0, "90+"))
MIN_DEVELOPMENT_SAMPLES = 8
MIN_VALIDATION_SAMPLES = 5


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _resolved_independent(rows, horizon):
    resolved = [
        row for row in (rows or [])
        if row.get("horizon") == horizon
        and row.get("resolved_at")
        and isinstance(row.get("correct"), bool)
    ]
    return _independent_rows(resolved, horizon)


def _split(rows):
    n = len(rows)
    if not n:
        return [], [], []
    dev_end = max(1, int(n * 0.60))
    val_end = max(dev_end, int(n * 0.80))
    if n >= 3:
        val_end = min(n - 1, max(dev_end + 1, val_end))
    return rows[:dev_end], rows[dev_end:val_end], rows[val_end:]


def _band(score):
    score = _finite(score)
    if score is None:
        return "unknown"
    for low, high, label in CONFIDENCE_BANDS:
        if low <= score < high:
            return label
    return "unknown"


def _payoff_components(rows):
    returns = []
    for row in rows:
        value = _finite(row.get("directional_return_pct"))
        if value is None:
            continue
        returns.append(value)
    total = len(rows)
    complete = total > 0 and len(returns) == total
    wins = [x for x in returns if x > 0]
    losses = [-x for x in returns if x <= 0]
    p_win = len(wins) / total if complete else None
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    gross_expectancy = None
    if complete:
        gross_expectancy = p_win * avg_win - (1.0 - p_win) * avg_loss
    return {
        "samples": total,
        "economic_evidence_complete": complete,
        "p_win": p_win,
        "average_win_pct": avg_win,
        "average_loss_pct": avg_loss,
        "gross_expectancy_pct": gross_expectancy,
    }


def _economic_metrics(rows, *, cost_pct):
    payoff = _payoff_components(rows)
    complete = payoff["economic_evidence_complete"]
    gross = payoff["gross_expectancy_pct"]
    stress = {}
    if complete:
        for multiplier in COST_STRESS_MULTIPLIERS:
            stressed_cost = float(cost_pct) * multiplier
            stress[f"{multiplier:g}x"] = round(float(gross) - stressed_cost, 4)
    base_expectancy = stress.get("1x") if complete else None
    worst_expectancy = stress.get(f"{max(COST_STRESS_MULTIPLIERS):g}x") if complete else None
    return {
        "samples": payoff["samples"],
        "economic_evidence_complete": complete,
        "p_win": round(payoff["p_win"], 4) if payoff["p_win"] is not None else None,
        "average_win_pct": round(payoff["average_win_pct"], 4) if complete else None,
        "average_loss_pct": round(payoff["average_loss_pct"], 4) if complete else None,
        "gross_expectancy_pct": round(gross, 4) if gross is not None else None,
        "round_trip_cost_pct": float(cost_pct),
        "expected_value_after_cost_pct": base_expectancy,
        "cost_stress_expected_value_pct": stress,
        "worst_case_expected_value_after_cost_pct": worst_expectancy,
    }


def _bucket_metrics(rows, *, cost_pct):
    buckets = {}
    for _, _, label in CONFIDENCE_BANDS:
        bucket = [row for row in rows if _band(row.get("score")) == label]
        buckets[label] = _economic_metrics(bucket, cost_pct=cost_pct)
    unknown = [row for row in rows if _band(row.get("score")) == "unknown"]
    if unknown:
        buckets["unknown"] = _economic_metrics(unknown, cost_pct=cost_pct)
    return buckets


def _positive_under_all_cost_stress(metrics):
    stress = metrics.get("cost_stress_expected_value_pct") or {}
    return bool(stress) and all(float(value) > 0.0 for value in stress.values())


def _negative_at_base_cost(metrics):
    value = metrics.get("expected_value_after_cost_pct")
    return value is not None and float(value) <= 0.0


def _candidates(dev_buckets, val_buckets):
    out = []
    for label in sorted(set(dev_buckets) | set(val_buckets)):
        dev = dev_buckets.get(label) or _economic_metrics([], cost_pct=0.0)
        val = val_buckets.get(label) or _economic_metrics([], cost_pct=0.0)
        status = "INSUFFICIENT_EVIDENCE"
        cost_robust = False
        if (
            dev["samples"] >= MIN_DEVELOPMENT_SAMPLES
            and val["samples"] >= MIN_VALIDATION_SAMPLES
            and dev["economic_evidence_complete"]
            and val["economic_evidence_complete"]
        ):
            dev_base = float(dev["expected_value_after_cost_pct"])
            val_base = float(val["expected_value_after_cost_pct"])
            if _negative_at_base_cost(dev) and _negative_at_base_cost(val):
                status = "RESTRICTIVE_WAIT_CANDIDATE"
                cost_robust = True
            elif dev_base > 0.0 and val_base > 0.0:
                cost_robust = _positive_under_all_cost_stress(dev) and _positive_under_all_cost_stress(val)
                status = "POSITIVE_ECONOMIC_CALIBRATION_CANDIDATE" if cost_robust else "FRAGILE_POSITIVE_ECONOMIC_EVIDENCE"
            else:
                status = "UNSTABLE_ECONOMIC_EVIDENCE"
        conservative_edge = None
        if dev.get("worst_case_expected_value_after_cost_pct") is not None and val.get("worst_case_expected_value_after_cost_pct") is not None:
            conservative_edge = round(min(
                float(dev["worst_case_expected_value_after_cost_pct"]),
                float(val["worst_case_expected_value_after_cost_pct"]),
            ), 4)
        out.append({
            "confidence_band": label,
            "development": dev,
            "validation": val,
            "candidate_status": status,
            "cost_stress_robust": cost_robust,
            "conservative_edge_pct": conservative_edge,
            "requires_untouched_oos": status in {"RESTRICTIVE_WAIT_CANDIDATE", "POSITIVE_ECONOMIC_CALIBRATION_CANDIDATE"},
            "trade_authority": False,
            "promotion_authority": False,
        })
    return out


def build_economic_calibration(rows, *, cost_pct=DEFAULT_ROUND_TRIP_COST_PCT):
    horizons = {}
    sealed = 0
    for horizon in ("24h", "7d"):
        independent = _resolved_independent(rows, horizon)
        development, validation, untouched_oos = _split(independent)
        sealed += len(untouched_oos)
        dev_buckets = _bucket_metrics(development, cost_pct=cost_pct)
        val_buckets = _bucket_metrics(validation, cost_pct=cost_pct)
        horizons[horizon] = {
            "independent_samples": len(independent),
            "development_samples": len(development),
            "validation_samples": len(validation),
            "untouched_oos_samples_sealed": len(untouched_oos),
            "development_overall": _economic_metrics(development, cost_pct=cost_pct),
            "validation_overall": _economic_metrics(validation, cost_pct=cost_pct),
            "confidence_bands": _candidates(dev_buckets, val_buckets),
        }
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("economic-calibration", "learning_diagnostics"),
        "formula": "P(win)*E(win) - P(loss)*E(loss) - round_trip_cost",
        "round_trip_cost_pct": float(cost_pct),
        "cost_stress_multipliers": list(COST_STRESS_MULTIPLIERS),
        "positive_candidate_policy": "development_and_validation_must_remain_positive_through_3x_fixed_cost_stress",
        "fragile_positive_policy": "base_cost_positive_but_one_or_more_predeclared_cost_stresses_non_positive",
        "untouched_oos_outcomes_scored": False,
        "untouched_oos_samples_sealed": sealed,
        "horizons": horizons,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_execution_authority": False,
    }

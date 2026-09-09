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


def _economic_metrics(rows, *, cost_pct):
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
    expectancy = None
    if complete:
        p_loss = 1.0 - p_win
        expectancy = p_win * avg_win - p_loss * avg_loss - float(cost_pct)
    return {
        "samples": total,
        "economic_evidence_complete": complete,
        "p_win": round(p_win, 4) if p_win is not None else None,
        "average_win_pct": round(avg_win, 4) if complete else None,
        "average_loss_pct": round(avg_loss, 4) if complete else None,
        "round_trip_cost_pct": float(cost_pct),
        "expected_value_after_cost_pct": round(expectancy, 4) if expectancy is not None else None,
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


def _candidates(dev_buckets, val_buckets):
    out = []
    for label in sorted(set(dev_buckets) | set(val_buckets)):
        dev = dev_buckets.get(label) or _economic_metrics([], cost_pct=0.0)
        val = val_buckets.get(label) or _economic_metrics([], cost_pct=0.0)
        status = "INSUFFICIENT_EVIDENCE"
        if (
            dev["samples"] >= MIN_DEVELOPMENT_SAMPLES
            and val["samples"] >= MIN_VALIDATION_SAMPLES
            and dev["economic_evidence_complete"]
            and val["economic_evidence_complete"]
        ):
            dev_ev = float(dev["expected_value_after_cost_pct"])
            val_ev = float(val["expected_value_after_cost_pct"])
            if dev_ev <= 0.0 and val_ev <= 0.0:
                status = "RESTRICTIVE_WAIT_CANDIDATE"
            elif dev_ev > 0.0 and val_ev > 0.0:
                status = "POSITIVE_ECONOMIC_CALIBRATION_CANDIDATE"
            else:
                status = "UNSTABLE_ECONOMIC_EVIDENCE"
        out.append({
            "confidence_band": label,
            "development": dev,
            "validation": val,
            "candidate_status": status,
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
        "untouched_oos_outcomes_scored": False,
        "untouched_oos_samples_sealed": sealed,
        "horizons": horizons,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_execution_authority": False,
    }

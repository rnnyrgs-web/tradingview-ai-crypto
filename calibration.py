"""Empirical forecast calibration that can only restrict live actions."""

from __future__ import annotations

import math

MIN_CALIBRATION_SAMPLES = 30
BIN_WIDTH = 10
RECENT_DETERIORATION_SAMPLES = 20
MIN_PRIOR_DETERIORATION_SAMPLES = 30
MAX_PRECISION_DROP = 0.15
MIN_RECENT_WILSON_LOWER = 0.45


def score_bin(score: float) -> tuple[int, int]:
    value = max(0.0, min(100.0, float(score)))
    lower = min(90, int(value // BIN_WIDTH) * BIN_WIDTH)
    return lower, lower + BIN_WIDTH


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = p + z * z / (2.0 * total)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def _ordered_resolved(rows):
    """Oldest->newest when timestamps exist; otherwise preserve caller order."""
    if rows and all(row.get("resolved_at") for row in rows):
        return sorted(rows, key=lambda row: str(row.get("resolved_at")))
    return list(rows)


def deterioration_assessment(rows, recent_samples=RECENT_DETERIORATION_SAMPLES,
                              minimum_prior=MIN_PRIOR_DETERIORATION_SAMPLES):
    """Detect recent collapse hidden by a stronger long-run calibration record.

    This gate is restrictive only. It requires enough genuinely resolved prior
    and recent forecasts before declaring deterioration. Small samples are
    reported as NOT_READY and do not independently block an otherwise valid
    calibration gate.
    """
    ordered = _ordered_resolved([row for row in rows if isinstance(row.get("correct"), bool)])
    recent_n = max(10, int(recent_samples))
    prior_n = max(20, int(minimum_prior))
    if len(ordered) < recent_n + prior_n:
        return {
            "ready": False,
            "deteriorating": False,
            "reason": "insufficient_recent_and_prior_samples",
            "recent_samples": min(recent_n, len(ordered)),
            "prior_samples": max(0, len(ordered) - recent_n),
        }

    recent = ordered[-recent_n:]
    prior = ordered[:-recent_n]
    recent_wins = sum(1 for row in recent if row["correct"])
    prior_wins = sum(1 for row in prior if row["correct"])
    recent_precision = recent_wins / len(recent)
    prior_precision = prior_wins / len(prior)
    recent_lower = wilson_lower_bound(recent_wins, len(recent))
    drop = prior_precision - recent_precision
    deteriorating = recent_lower < MIN_RECENT_WILSON_LOWER and drop >= MAX_PRECISION_DROP
    return {
        "ready": True,
        "deteriorating": deteriorating,
        "reason": "recent_precision_deterioration" if deteriorating else "ok",
        "recent_samples": len(recent),
        "prior_samples": len(prior),
        "recent_correct": recent_wins,
        "prior_correct": prior_wins,
        "recent_precision": round(recent_precision, 4),
        "prior_precision": round(prior_precision, 4),
        "recent_precision_95pct_lower": round(recent_lower, 4),
        "precision_drop": round(drop, 4),
        "policy": {
            "max_precision_drop": MAX_PRECISION_DROP,
            "min_recent_wilson_lower": MIN_RECENT_WILSON_LOWER,
        },
    }


def calibration_assessment(score, horizon, resolved, regime=None, minimum_samples=MIN_CALIBRATION_SAMPLES):
    """Prefer regime evidence when populated; otherwise use the horizon score bin."""
    lower, upper = score_bin(score)
    comparable = [
        row for row in resolved
        if row.get("horizon") == horizon
        and lower <= float(row.get("score") or 0.0)
        and (float(row.get("score") or 0.0) < upper or upper == 100)
        and isinstance(row.get("correct"), bool)
    ]
    regime_rows = [row for row in comparable if row.get("market_regime") == regime]
    use_regime = len(regime_rows) >= minimum_samples
    selected = regime_rows if use_regime else comparable
    successes = sum(1 for row in selected if row["correct"])
    total = len(selected)
    lower_bound = wilson_lower_bound(successes, total)
    ready = total >= minimum_samples
    deterioration = deterioration_assessment(selected)
    calibration_pass = bool(ready and lower_bound >= 0.50)
    allows_live = calibration_pass and not deterioration.get("deteriorating", False)
    return {
        "ready": ready,
        "scope": "horizon_regime_score_bin" if use_regime else "horizon_score_bin",
        "horizon": horizon,
        "score_bin": [lower, upper],
        "samples": total,
        "correct": successes,
        "empirical_precision": round(successes / total, 4) if ready else None,
        "precision_95pct_lower": round(lower_bound, 4) if ready else None,
        "minimum_samples": minimum_samples,
        "deterioration": deterioration,
        "allows_live_action": bool(allows_live),
        "restriction_reason": (
            "RECENT_FORECAST_DETERIORATION" if deterioration.get("deteriorating") else
            "CALIBRATION_NOT_READY_OR_WEAK" if not calibration_pass else None
        ),
    }


def calibration_summary(resolved):
    summaries = []
    for horizon in ("24h", "7d"):
        rows = [row for row in resolved if row.get("horizon") == horizon and isinstance(row.get("correct"), bool)]
        successes = sum(1 for row in rows if row["correct"])
        summaries.append({
            "horizon": horizon,
            "samples": len(rows),
            "precision": round(successes / len(rows), 4) if rows else None,
            "precision_95pct_lower": round(wilson_lower_bound(successes, len(rows)), 4) if rows else None,
            "deterioration": deterioration_assessment(rows),
        })
    return {"ok": True, "policy": "Calibration and deterioration detection can restrict but never authorize a strategy.", "horizons": summaries}

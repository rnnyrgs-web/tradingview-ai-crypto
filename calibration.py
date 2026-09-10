"""Empirical forecast calibration that can only restrict live actions.

Readiness, confidence bounds and deterioration checks use deterministic,
full-horizon, non-overlapping resolved forecasts. Frequent scans inside the same
forecast outcome window are correlated observations and may not inflate evidence.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from config import OPPORTUNITY_HORIZONS

MIN_CALIBRATION_SAMPLES = 30
BIN_WIDTH = 10
RECENT_DETERIORATION_SAMPLES = 20
MIN_PRIOR_DETERIORATION_SAMPLES = 30
MAX_PRECISION_DROP = 0.15
MIN_RECENT_WILSON_LOWER = 0.45
HORIZON_SPAN = {
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "72h": timedelta(hours=72),
    "7d": timedelta(days=7),
}


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


def _timestamp(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _stable_identity(row):
    identity = row.get("strategy_identity")
    if isinstance(identity, dict):
        identity = identity.get("fingerprint") or identity.get("strategy_family") or ""
    return (
        str(row.get("scan_id") or ""),
        str(row.get("symbol") or ""),
        str(identity or ""),
        str(row.get("direction") or ""),
        str(row.get("score") or ""),
    )


def _independent_rows(rows, horizon):
    """Return outcome-blind full-horizon non-overlapping resolved forecasts.

    ``due_at`` is immutable forecast-time metadata. Forecast origin is therefore
    reconstructed as ``due_at - horizon``. Missing or malformed chronology cannot
    contribute to calibration readiness; this deliberately fails closed.
    """
    span = HORIZON_SPAN.get(horizon)
    if span is None:
        return []
    valid = []
    for row in rows or []:
        if not isinstance(row.get("correct"), bool):
            continue
        due_at = _timestamp(row.get("due_at"))
        resolved_at = _timestamp(row.get("resolved_at"))
        if due_at is None or resolved_at is None or resolved_at < due_at:
            continue
        origin = due_at - span
        valid.append((origin, due_at, _stable_identity(row), row))
    valid.sort(key=lambda item: (item[0], item[1], item[2]))

    selected = []
    covered_until = None
    for origin, due_at, _identity, row in valid:
        if covered_until is not None and origin < covered_until:
            continue
        selected.append(row)
        covered_until = due_at
    return selected


def _ordered_resolved(rows):
    """Oldest->newest when timestamps exist; otherwise preserve caller order."""
    if rows and all(row.get("resolved_at") for row in rows):
        return sorted(rows, key=lambda row: str(row.get("resolved_at")))
    return list(rows)


def deterioration_assessment(rows, recent_samples=RECENT_DETERIORATION_SAMPLES,
                              minimum_prior=MIN_PRIOR_DETERIORATION_SAMPLES):
    """Detect recent collapse in an already-independent resolved sample stream."""
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
    """Restrictive empirical gate based only on independent forecast windows."""
    lower, upper = score_bin(score)
    comparable_raw = [
        row for row in resolved
        if row.get("horizon") == horizon
        and lower <= float(row.get("score") or 0.0)
        and (float(row.get("score") or 0.0) < upper or upper == 100)
        and isinstance(row.get("correct"), bool)
    ]
    regime_raw = [row for row in comparable_raw if row.get("market_regime") == regime]
    regime_independent = _independent_rows(regime_raw, horizon)
    comparable_independent = _independent_rows(comparable_raw, horizon)
    use_regime = len(regime_independent) >= minimum_samples
    selected = regime_independent if use_regime else comparable_independent
    raw_selected_count = len(regime_raw) if use_regime else len(comparable_raw)

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
        "independent_samples": total,
        "raw_matching_rows": raw_selected_count,
        "correct": successes,
        "empirical_precision": round(successes / total, 4) if ready else None,
        "precision_95pct_lower": round(lower_bound, 4) if ready else None,
        "minimum_samples": minimum_samples,
        "sample_sufficiency_basis": "non_overlapping_full_horizon_forecasts_reconstructed_from_due_at",
        "raw_rows_are_independent": False,
        "deterioration": deterioration,
        "allows_live_action": bool(allows_live),
        "restriction_reason": (
            "RECENT_FORECAST_DETERIORATION" if deterioration.get("deteriorating") else
            "CALIBRATION_NOT_READY_OR_WEAK" if not calibration_pass else None
        ),
    }


def calibration_summary(resolved):
    summaries = []
    for horizon in OPPORTUNITY_HORIZONS:
        raw_rows = [row for row in resolved if row.get("horizon") == horizon and isinstance(row.get("correct"), bool)]
        rows = _independent_rows(raw_rows, horizon)
        successes = sum(1 for row in rows if row["correct"])
        summaries.append({
            "horizon": horizon,
            "samples": len(rows),
            "independent_samples": len(rows),
            "raw_resolved_rows": len(raw_rows),
            "precision": round(successes / len(rows), 4) if rows else None,
            "precision_95pct_lower": round(wilson_lower_bound(successes, len(rows)), 4) if rows else None,
            "deterioration": deterioration_assessment(rows),
            "raw_rows_are_independent": False,
        })
    return {
        "ok": True,
        "policy": "Calibration and deterioration detection can restrict but never authorize a strategy; readiness and confidence use non-overlapping full-horizon forecasts only.",
        "horizons": summaries,
    }

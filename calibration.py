"""Empirical forecast calibration that can only restrict live actions."""

from __future__ import annotations

import math

MIN_CALIBRATION_SAMPLES = 30
BIN_WIDTH = 10


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
        "allows_live_action": bool(ready and lower_bound >= 0.50),
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
        })
    return {"ok": True, "policy": "Calibration can restrict but never authorize a strategy.", "horizons": summaries}

"""Research-only selective precision analysis for resolved forecasts.

Measures whether stricter, predeclared confidence/consensus subsets actually
improve empirical precision. This module never converts a score into a claimed
probability and has no trade or promotion authority.
"""

from __future__ import annotations

from calibration import wilson_lower_bound

MIN_SELECTIVE_SAMPLES = 30
PREDECLARED_THRESHOLDS = (60.0, 70.0, 80.0, 90.0)


def _resolved(rows, horizon):
    return [
        row for row in rows or []
        if row.get("horizon") == horizon and isinstance(row.get("correct"), bool)
    ]


def _metrics(rows):
    total = len(rows)
    correct = sum(1 for row in rows if row["correct"])
    return {
        "samples": total,
        "correct": correct,
        "precision": round(correct / total, 4) if total else None,
        "precision_95pct_lower": round(wilson_lower_bound(correct, total), 4) if total else None,
    }


def selective_precision_assessment(rows, horizon, *, minimum_samples=MIN_SELECTIVE_SAMPLES):
    """Compare fixed confidence cutoffs without selecting a winner from the holdout.

    Thresholds are fixed in code before evaluation. Results are descriptive and
    research-only; a better-looking subset cannot authorize production trading.
    """
    base = _resolved(rows, horizon)
    baseline = _metrics(base)
    subsets = []
    for threshold in PREDECLARED_THRESHOLDS:
        selected = []
        for row in base:
            try:
                score = float(row.get("score") or 0.0)
            except (TypeError, ValueError):
                continue
            if score < threshold:
                continue
            # If independent market consensus was recorded, require it to have
            # been reliable. Missing historical fields are not fabricated.
            consensus = row.get("market_consensus_reliable")
            if consensus is False:
                continue
            selected.append(row)
        metrics = _metrics(selected)
        ready = metrics["samples"] >= int(minimum_samples)
        baseline_precision = baseline["precision"]
        lift = None
        if ready and baseline_precision is not None and metrics["precision"] is not None:
            lift = round(metrics["precision"] - baseline_precision, 4)
        subsets.append({
            "minimum_score": threshold,
            **metrics,
            "ready": ready,
            "precision_lift_vs_all_resolved": lift,
        })
    return {
        "horizon": horizon,
        "baseline": baseline,
        "subsets": subsets,
        "minimum_samples": int(minimum_samples),
        "thresholds_predeclared": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "probability_claim": False,
    }


def selective_precision_summary(rows):
    return {
        "ok": True,
        "policy": "Selective precision is descriptive research only; thresholds cannot be chosen from untouched/forward outcomes to authorize trading.",
        "horizons": [selective_precision_assessment(rows, horizon) for horizon in ("24h", "7d")],
    }

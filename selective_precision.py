"""Research-only selective precision analysis for resolved forecasts.

Measures whether stricter, predeclared confidence/consensus subsets actually
improve empirical precision. This module never converts a score into a claimed
probability and has no trade or promotion authority.

Resolved rows are de-overlapped before confidence bounds or sample-readiness
claims are computed. Production scans can occur much more frequently than the
24h/7d forecast horizon, so counting every resolved row as statistically
independent would materially overstate evidence strength.
"""

from __future__ import annotations

from datetime import timedelta

from calibration import wilson_lower_bound
from utils import parse_dt

MIN_SELECTIVE_SAMPLES = 30
PREDECLARED_THRESHOLDS = (60.0, 70.0, 80.0, 90.0)
HORIZON_SPAN = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


def _fingerprint(row):
    identity = row.get("strategy_identity")
    return str(identity.get("fingerprint", "")) if isinstance(identity, dict) else ""


def _score(row):
    try:
        return float(row.get("score") or 0.0)
    except (TypeError, ValueError):
        return None


def _resolved(rows, horizon):
    return [
        row for row in rows or []
        if row.get("horizon") == horizon and isinstance(row.get("correct"), bool)
    ]


def _independent_rows(rows, horizon):
    """Return deterministic, full-horizon, non-overlapping resolved forecasts.

    The production ledger has no ``created_at`` column. ``due_at`` is immutable
    and is written at forecast time as ``forecast_time + horizon``; therefore the
    forecast origin can be reconstructed safely as ``due_at - horizon``.

    Tie-breaking is deliberately outcome-blind so correctness cannot influence
    which row survives a same-origin collision.
    """
    span = HORIZON_SPAN.get(horizon)
    if span is None:
        return []

    valid = []
    for row in rows or []:
        if not row.get("due_at") or not row.get("resolved_at"):
            continue
        try:
            due = parse_dt(row["due_at"])
            resolved = parse_dt(row["resolved_at"])
        except (TypeError, ValueError, OverflowError):
            continue
        if resolved < due:
            continue
        origin = due - span
        score = _score(row)
        valid.append((origin, due, _fingerprint(row), score if score is not None else float("-inf"), row))

    valid.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    selected = []
    next_allowed = None
    for origin, _due, _fingerprint_value, _score_value, row in valid:
        if next_allowed is not None and origin < next_allowed:
            continue
        selected.append(row)
        next_allowed = origin + span
    return selected


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
    Confidence/readiness statistics use only non-overlapping full-horizon rows.
    """
    raw_base = _resolved(rows, horizon)
    base = _independent_rows(raw_base, horizon)
    baseline = _metrics(base)
    baseline["raw_resolved_rows"] = len(raw_base)
    subsets = []
    for threshold in PREDECLARED_THRESHOLDS:
        candidates = []
        for row in raw_base:
            score = _score(row)
            if score is None or score < threshold:
                continue
            # If independent market consensus was recorded, require it to have
            # been reliable. Missing historical fields are not fabricated.
            consensus = row.get("market_consensus_reliable")
            if consensus is False:
                continue
            candidates.append(row)
        selected = _independent_rows(candidates, horizon)
        metrics = _metrics(selected)
        metrics["raw_matching_rows"] = len(candidates)
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
        "non_overlapping_full_horizon_samples_only": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "probability_claim": False,
    }


def selective_precision_summary(rows):
    return {
        "ok": True,
        "policy": "Selective precision is descriptive research only; confidence/readiness uses non-overlapping full-horizon rows and thresholds cannot be chosen from untouched/forward outcomes to authorize trading.",
        "horizons": [selective_precision_assessment(rows, horizon) for horizon in ("24h", "7d")],
    }

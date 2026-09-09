"""Research-only ensemble diversity diagnostics.

Near-duplicate strategies must not be treated as independent confirmation. This
module measures matched forward error agreement between immutable strategy
identities and nominates only research candidates for redundancy penalties.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from signal_development import objective_reference

MIN_MATCHED_SAMPLES = 8
REDUNDANT_ERROR_AGREEMENT = 0.85


def _resolved(rows):
    return [
        row for row in (rows or [])
        if row.get("resolved_at")
        and isinstance(row.get("correct"), bool)
        and row.get("horizon") in {"24h", "7d"}
        and row.get("due_at")
        and row.get("symbol")
        and row.get("strategy_identity")
    ]


def _matched(rows):
    buckets = defaultdict(dict)
    for row in _resolved(rows):
        key = (str(row["horizon"]), str(row["symbol"]), str(row["due_at"]))
        buckets[key][str(row["strategy_identity"])] = row
    return buckets


def _pair_report(a, b, matched_rows):
    both = []
    for strategies in matched_rows.values():
        if a in strategies and b in strategies:
            both.append((strategies[a], strategies[b]))
    n = len(both)
    if not n:
        return {
            "strategy_a": a,
            "strategy_b": b,
            "matched_samples": 0,
            "error_agreement_rate": None,
            "disagreement_rate": None,
            "candidate_status": "INSUFFICIENT_MATCHED_EVIDENCE",
        }
    agreement = 0
    disagreement = 0
    joint_errors = 0
    for ra, rb in both:
        ea = ra.get("correct") is False
        eb = rb.get("correct") is False
        if ea == eb:
            agreement += 1
        else:
            disagreement += 1
        if ea and eb:
            joint_errors += 1
    agreement_rate = agreement / n
    status = "INSUFFICIENT_MATCHED_EVIDENCE"
    if n >= MIN_MATCHED_SAMPLES:
        status = "REDUNDANT_MECHANISM_RESEARCH_CANDIDATE" if agreement_rate >= REDUNDANT_ERROR_AGREEMENT else "DIVERSITY_EVIDENCE_PRESENT"
    return {
        "strategy_a": a,
        "strategy_b": b,
        "matched_samples": n,
        "error_agreement_rate": round(agreement_rate, 4),
        "disagreement_rate": round(disagreement / n, 4),
        "joint_error_rate": round(joint_errors / n, 4),
        "candidate_status": status,
        "treat_as_independent_confirmation": False if status == "REDUNDANT_MECHANISM_RESEARCH_CANDIDATE" else None,
        "requires_fresh_validation": True,
    }


def build_ensemble_diversity(rows):
    matched_rows = _matched(rows)
    strategies = sorted({s for mapping in matched_rows.values() for s in mapping})
    pairs = [_pair_report(a, b, matched_rows) for a, b in combinations(strategies, 2)]
    pairs.sort(key=lambda x: (
        0 if x["candidate_status"] == "REDUNDANT_MECHANISM_RESEARCH_CANDIDATE" else 1,
        -x["matched_samples"],
        x["strategy_a"],
        x["strategy_b"],
    ))
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("ensemble-diversity", "learning_diagnostics"),
        "matched_forecast_endpoints": len(matched_rows),
        "strategy_count": len(strategies),
        "pairs": pairs,
        "policy": "Redundant error behavior may reduce research weight only after validation; model count never creates independent evidence by itself.",
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
    }

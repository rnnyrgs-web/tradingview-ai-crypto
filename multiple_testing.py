"""Restrictive search-breadth firewall for autonomous quant research.

This is deliberately not presented as a formal p-value/FDR correction because
bootstrap probability-positive is not a null-hypothesis p-value. Instead it is
a transparent conservative evidence penalty: as the declared number of distinct
strategy/parameter hypotheses grows, promotion review requires more independent
OOS trades and stronger bootstrap support. The gate can only reject/demote.
"""

from __future__ import annotations

import copy
import math


def evidence_requirements(trial_count: int) -> dict:
    if not isinstance(trial_count, int) or trial_count < 1:
        raise ValueError("trial_count must be a positive integer")
    breadth = math.log2(max(1, trial_count))
    return {
        "declared_trial_count": trial_count,
        "min_combined_oos_trades": 15 + int(math.ceil(2.0 * breadth)),
        "min_bootstrap_probability_positive": min(0.99, 0.80 + 0.02 * breadth),
        "requires_positive_bootstrap_p05": True,
        "policy_kind": "conservative_search_breadth_penalty_not_formal_p_value_correction",
    }


def assess_strategy(strategy: dict, trial_count: int) -> dict:
    req = evidence_requirements(trial_count)
    reasons = []
    if not isinstance(strategy, dict):
        return {"passed": False, "reasons": ["malformed_strategy_evidence"], "requirements": req}

    validation = strategy.get("validation") or {}
    holdout = strategy.get("holdout_test") or {}
    robustness = strategy.get("robustness") or {}
    monte = robustness.get("monte_carlo") or {}

    try:
        oos_trades = int(validation.get("trades") or 0) + int(holdout.get("trades") or 0)
        probability_positive = float(monte.get("probability_positive"))
        p05 = float(monte.get("p05_sum_returns_pct"))
    except (TypeError, ValueError):
        return {"passed": False, "reasons": ["malformed_multiple_testing_evidence"], "requirements": req}

    if not math.isfinite(probability_positive) or not math.isfinite(p05):
        reasons.append("nonfinite_multiple_testing_evidence")
    if oos_trades < req["min_combined_oos_trades"]:
        reasons.append("insufficient_oos_depth_for_search_breadth")
    if probability_positive < req["min_bootstrap_probability_positive"]:
        reasons.append("bootstrap_support_too_weak_for_search_breadth")
    if p05 <= 0:
        reasons.append("bootstrap_lower_bound_not_positive")

    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "requirements": req,
        "observed": {
            "combined_oos_trades": oos_trades,
            "bootstrap_probability_positive": probability_positive,
            "bootstrap_p05_sum_returns_pct": p05,
        },
        "restrictive_only": True,
        "can_authorize_by_itself": False,
    }


def apply_registry_firewall(registry_result: dict, trial_count: int) -> dict:
    """Return a copied registry with search-breadth failures demoted."""
    out = copy.deepcopy(registry_result)
    rows = out.get("registry") or []
    for row in rows:
        gate = assess_strategy(row, trial_count)
        row["multiple_testing_gate"] = gate
        if row.get("eligible_for_promotion_review") is True and not gate["passed"]:
            row["eligible_for_promotion_review"] = False
            row["status"] = "RESEARCH_ONLY"
            quality = row.setdefault("quality_gate", {})
            reasons = list(quality.get("reasons") or [])
            if "multiple_testing_evidence_insufficient" not in reasons:
                reasons.append("multiple_testing_evidence_insufficient")
            quality["reasons"] = reasons
    out["declared_hypothesis_trials"] = trial_count
    out["multiple_testing_policy"] = evidence_requirements(trial_count)
    out["eligible_count"] = sum(1 for row in rows if row.get("eligible_for_promotion_review") is True)
    return out

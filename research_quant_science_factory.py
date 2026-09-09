"""Scientific research-only factory for accuracy-focused quant experiments.

Builds on resolved-signal diagnostics and the immutable experiment factory, then
adds predeclared scientific design metadata and bounded hypothesis-family breadth.
It never executes a strategy, changes production thresholds, or creates trade or
promotion authority.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from research_experiment_factory import MAX_EXPERIMENTS, build_experiment_queue
from signal_development import objective_reference

MAX_PER_METHOD = 4
MASSIVE_VIRTUAL_RESEARCH_CONSTRAINTS = {
    "logical_idea_space_unbounded": True,
    "physical_heavy_concurrency_may_increase": False,
    "max_predeclared_searches_per_hypothesis": 1,
    "max_candidate_mutations_per_hypothesis": 1,
    "parameter_mining_allowed": False,
    "untouched_oos_reuse_allowed": False,
    "forward_evidence_pooled_with_oos": False,
    "multiple_testing_firewall_required": True,
    "independent_replication_required": True,
    "genuine_forward_replication_required": True,
    "duplicate_hypothesis_research_penalty_required": True,
    "paid_compute_escalation_allowed": False,
    "monthly_infrastructure_ceiling_usd": 30,
    "trade_authority": False,
    "promotion_authority": False,
    "strategy_mutation_authority": False,
}

METHOD_BY_DIMENSION = {
    "score_band": "selective_abstention_calibration",
    "market_regime": "regime_conditioned_abstention",
    "direction": "direction_specific_false_positive_filter",
    "strategy_identity": "strategy_deterioration_challenger",
    "horizon": "horizon_specific_calibration",
}

DISPATCHABLE_METHODS = {
    "selective_abstention_calibration",
    "regime_conditioned_abstention",
    "direction_specific_false_positive_filter",
    "strategy_deterioration_challenger",
}


def _family_id(method: str, dimension: str, group: str, horizon: str) -> str:
    raw = f"{method}|{dimension}|{group}|{horizon}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _scientific_design(experiment: dict) -> dict:
    dimension = str(experiment.get("dimension") or "unknown")
    group = str(experiment.get("group") or "unknown")
    horizon = str(experiment.get("target_horizon") or "both")
    method = METHOD_BY_DIMENSION.get(dimension, "restrictive_challenger_audit")
    abstention_first = method in {
        "selective_abstention_calibration",
        "regime_conditioned_abstention",
        "direction_specific_false_positive_filter",
        "horizon_specific_calibration",
    }
    dispatchable = method in DISPATCHABLE_METHODS
    return {
        "research_method": method,
        "hypothesis_family_id": _family_id(method, dimension, group, horizon),
        "primary_endpoint": "after_cost_selective_precision_on_untouched_oos",
        "secondary_endpoints": [
            "after_cost_expectancy",
            "actionable_coverage",
            "false_positive_rate",
            "calibration_error",
        ],
        "guardrail_endpoints": [
            "max_drawdown_not_materially_worse",
            "tail_loss_not_materially_worse",
            "point_in_time_universe_pass",
            "multiple_testing_firewall_pass",
        ],
        "minimum_effect_to_continue": {
            "precision_absolute_improvement": 0.02,
            "after_cost_expectancy_must_be_positive": True,
        },
        "minimum_evaluation_samples": 8,
        "minimum_actionable_coverage": 0.25,
        "predeclared_search_budget": 1,
        "max_candidate_mutations": 1,
        "abstention_first": abstention_first,
        "executor_kind": "restrictive_group_abstention_v1" if dispatchable else "design_only",
        "dispatchable_now": dispatchable,
        "parameter_mining_allowed": False,
        "untouched_oos_reuse_allowed": False,
        "forward_evidence_pooled_with_oos": False,
        "multiple_testing_firewall_required": True,
        "independent_replication_required": True,
        "genuine_forward_replication_required": True,
        "duplicate_hypothesis_research_penalty_required": True,
        "paid_compute_escalation_allowed": False,
        "idea_generation_counts_as_evidence": False,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
    }


def build_quant_science_queue(diagnostics: dict, memory: dict | None = None, *, limit: int = MAX_EXPERIMENTS) -> dict:
    """Return a bounded, diversified queue of scientifically predeclared experiments."""
    base = build_experiment_queue(diagnostics, memory, limit=MAX_EXPERIMENTS)
    candidates = []
    for row in base.get("experiments") or []:
        enriched = dict(row)
        enriched["science_design"] = _scientific_design(row)
        candidates.append(enriched)

    candidates.sort(
        key=lambda row: (
            -float(row.get("information_priority") or 0.0),
            -int(row.get("source_independent_samples") or 0),
            str(row.get("experiment_id") or ""),
        )
    )

    method_counts = defaultdict(int)
    selected = []
    bounded_limit = max(0, min(int(limit), MAX_EXPERIMENTS))
    for row in candidates:
        method = row["science_design"]["research_method"]
        if method_counts[method] >= MAX_PER_METHOD:
            continue
        method_counts[method] += 1
        selected.append(row)
        if len(selected) >= bounded_limit:
            break

    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("quant-science-factory", "experiment_factory"),
        "experiment_count": len(selected),
        "experiments": selected,
        "method_counts": dict(sorted(method_counts.items())),
        "max_per_method": MAX_PER_METHOD,
        "massive_virtual_research_constraints": dict(MASSIVE_VIRTUAL_RESEARCH_CONSTRAINTS),
        "scientific_policy": (
            "Resolved errors generate predeclared restrictive hypotheses. Virtual idea generation may scale very large, "
            "but executable breadth stays bounded and scarce heavy compute remains unchanged. Every hypothesis gets one "
            "predeclared search and at most one candidate mutation; parameter mining, OOS reuse, OOS/forward pooling and "
            "paid-compute escalation are forbidden. Multiple-testing protection, independent replication and genuine "
            "forward replication are mandatory before any promotion path can exist. Production authority remains false."
        ),
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }

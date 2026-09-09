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

METHOD_BY_DIMENSION = {
    "score_band": "selective_abstention_calibration",
    "market_regime": "regime_conditioned_abstention",
    "direction": "direction_specific_false_positive_filter",
    "strategy_identity": "strategy_deterioration_challenger",
    "horizon": "horizon_specific_calibration",
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
        "predeclared_search_budget": 1,
        "abstention_first": abstention_first,
        "parameter_mining_allowed": False,
        "untouched_oos_reuse_allowed": False,
        "forward_evidence_pooled_with_oos": False,
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
        "objective": objective_reference("quant-science-factory", "quant_science_factory"),
        "experiment_count": len(selected),
        "experiments": selected,
        "method_counts": dict(sorted(method_counts.items())),
        "max_per_method": MAX_PER_METHOD,
        "scientific_policy": (
            "Resolved errors generate predeclared restrictive hypotheses. Breadth is capped per method to reduce "
            "parameter mining and multiple-testing burden. Primary decisions use untouched OOS after realistic "
            "costs; forward evidence remains separate and production authority remains false."
        ),
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }

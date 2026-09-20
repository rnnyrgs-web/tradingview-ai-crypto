"""Bounded research-only scheduler for deterministic heavy experiment candidates.

The scheduler ranks and admits already-predeclared experiment specs. It never
mutates strategies, promotes a model, places orders, or raises heavy concurrency.
Blocked/natural-history experiments are excluded so scarce compute can be spent on
experiments capable of producing actionable evidence now.
"""

from __future__ import annotations

from math import isfinite
from copy import deepcopy

from profitability_learning.contracts import SAFE, number
from research_quant_science_factory import verified_strategy_semantic_fingerprint

from signal_development import objective_reference, priority_score, validate_task_contract

MAX_HEAVY_EXPERIMENT_SLOTS = 1
BLOCKED_EVIDENCE_STATES = {
    "BLOCKED_NATURAL_HISTORY_ACCUMULATION",
    "BLOCKED_INSUFFICIENT_HISTORY",
    "BLOCKED_MISSING_PROSPECTIVE_EVIDENCE",
}


def _finite(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _science_design(experiment: dict) -> dict:
    value = experiment.get("science_design")
    return value if isinstance(value, dict) else {}


def _eligible(experiment: dict) -> bool:
    if not isinstance(experiment, dict):
        return False
    if experiment.get("compute_class") != "heavy_candidate":
        return False
    if experiment.get("status") != "QUEUED_RESEARCH_ONLY":
        return False
    if experiment.get("blocked_reason"):
        return False
    if _learning_factor(experiment) <= 0:
        return False
    if str(experiment.get("evidence_readiness") or "") in BLOCKED_EVIDENCE_STATES:
        return False
    if not experiment.get("experiment_id") or not experiment.get("required_validation"):
        return False
    try:
        validate_task_contract(experiment)
    except RuntimeError:
        return False
    forbidden = ("automatic_execution_authority", "strategy_mutation_authority", "trade_authority", "promotion_authority")
    if not all(experiment.get(flag) is False for flag in forbidden):
        return False
    design = _science_design(experiment)
    # Learned admission is allowed to change scarce-compute eligibility and
    # priority. It must therefore carry a complete code-bound strategy/design;
    # legacy compatibility cannot turn caller-asserted feedback into authority.
    if "learning_feedback" in experiment and not design:
        return False
    if design:
        if design.get("research_only") is not True:
            return False
        if design.get("parameter_mining_allowed") is not False:
            return False
        if design.get("untouched_oos_reuse_allowed") is not False:
            return False
        if design.get("forward_evidence_pooled_with_oos") is not False:
            return False
        if design.get("predeclared_search_budget") != 1:
            return False
        if design.get("max_candidate_mutations") != 1:
            return False
        if design.get("multiple_testing_firewall_required") is not True:
            return False
        if design.get("independent_replication_required") is not True:
            return False
        if design.get("genuine_forward_replication_required") is not True:
            return False
        if design.get("duplicate_hypothesis_research_penalty_required") is not True:
            return False
        if design.get("paid_compute_escalation_allowed") is not False:
            return False
        if design.get("idea_generation_counts_as_evidence") is not False:
            return False
        if int(experiment.get("source_independent_samples") or 0) < int(design.get("minimum_evaluation_samples") or 0):
            return False
        # New quant-science designs must explicitly identify an implemented,
        # research-only executor before they can consume scarce heavy compute.
        if design.get("dispatchable_now") is False:
            return False
        if "dispatchable_now" in design and not design.get("executor_kind"):
            return False
        try:
            verified_strategy_semantic_fingerprint(experiment)
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _learning_factor(row: dict) -> float:
    """Consume bounded feedback; invalid/rejected evidence cannot authorize work."""
    if "learning_feedback" not in row:
        return 1.0  # Existing queues without configured learning remain compatible.
    feedback = row["learning_feedback"]
    if (not isinstance(feedback, dict)
            or any(feedback.get(key) is not value for key, value in SAFE.items())
            or feedback.get("changes_eligibility") is not False
            or not isinstance(feedback.get("reason"), str)
            or feedback.get("reason") not in {"no_matched_completion",
                "prior_completion_requires_new_evidence", "matched_family_economic_evidence",
                "matched_semantic_economic_evidence"}):
        return 0.0
    try:
        factor = number(feedback.get("factor"), "learning factor", minimum=0)
    except ValueError:
        return 0.0
    # Current bounded family boost (1.3) times component boost (1.15) < 1.5.
    return factor if factor <= 1.5 else 0.0


def _base_profitability_priority(row: dict) -> float:
    factors = row.get("priority_factors") or {}
    return priority_score(
        expected_incremental_after_cost_profitability_impact=factors.get("expected_incremental_after_cost_profitability_impact", 0),
        expected_information_falsification_value=factors.get("expected_information_falsification_value", 0),
        probability_actionable_evidence=factors.get("probability_actionable_evidence", 0),
        compute_api_cost_units=factors.get("compute_api_cost_units", 1),
    )


def _profitability_priority(row: dict) -> float:
    return _base_profitability_priority(row) * _learning_factor(row)


def _signal_quality_secondary(row: dict) -> float:
    factors = row.get("priority_factors") or {}
    return max(0.0, min(1.0, _finite(factors.get("expected_genuine_signal_quality_impact"))))


def _abstention_first(row: dict) -> int:
    return 1 if _science_design(row).get("abstention_first") is True else 0


def build_heavy_dispatch_plan(experiment_queue: dict, *, running_experiment_ids=None, max_slots: int = MAX_HEAVY_EXPERIMENT_SLOTS) -> dict:
    """Choose the highest-value currently actionable experiment for scarce heavy compute."""
    running = {str(value) for value in (running_experiment_ids or []) if value}
    slots = max(0, min(int(max_slots), MAX_HEAVY_EXPERIMENT_SLOTS))
    rows = experiment_queue.get("experiments") if isinstance(experiment_queue, dict) else []
    all_rows = list(rows or [])
    candidates = [row for row in all_rows if _eligible(row) and str(row.get("experiment_id")) not in running]
    blocked_count = sum(1 for row in all_rows if isinstance(row, dict) and (row.get("blocked_reason") or str(row.get("evidence_readiness") or "") in BLOCKED_EVIDENCE_STATES))
    candidates.sort(
        key=lambda row: (
            -_profitability_priority(row),
            -_signal_quality_secondary(row),
            -_abstention_first(row),
            -int(row.get("source_independent_samples") or 0),
            str(row.get("experiment_id")),
        )
    )
    selected = []
    for row in candidates[:slots]:
        design = _science_design(row)
        selected.append({
            "experiment_id": str(row["experiment_id"]),
            "profitability_priority_score": _profitability_priority(row),
            "base_profitability_priority_score": _base_profitability_priority(row),
            "learning_feedback": deepcopy(row.get("learning_feedback")),
            "signal_quality_secondary_score": _signal_quality_secondary(row),
            "priority_factors": dict(row.get("priority_factors") or {}),
            "information_priority": _finite(row.get("information_priority")),
            "source_samples": int(row.get("source_samples") or 0),
            "source_independent_samples": int(row.get("source_independent_samples") or 0),
            "dimension": str(row.get("dimension") or "unknown"),
            "group": str(row.get("group") or "unknown"),
            "target_horizon": row.get("target_horizon"),
            "hypothesis": row.get("hypothesis"),
            "research_method": design.get("research_method"),
            "executor_kind": design.get("executor_kind"),
            "executor_implementation_id": design.get("executor_implementation_id"),
            "primary_endpoint": design.get("primary_endpoint"),
            "abstention_first": bool(design.get("abstention_first")),
            "falsification_criteria": list(row.get("falsification_criteria") or []),
            "status": "ADMITTED_FOR_HEAVY_RESEARCH",
            "required_validation": list(row.get("required_validation") or []),
            "trade_authority": False,
            "promotion_authority": False,
            "strategy_mutation_authority": False,
        })
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("heavy-experiment-scheduler", "heavy_experiment_scheduler"),
        "heavy_slot_limit": slots,
        "running_experiment_count": len(running),
        "eligible_candidate_count": len(candidates),
        "blocked_candidate_count": blocked_count,
        "selected_count": len(selected),
        "selected": selected,
        "priority_policy": "expected incremental after-cost profitability impact x information/falsification value x probability of actionable evidence / compute/API cost, multiplied by bounded validated learning feedback when present; rejected or invalid feedback is ineligible; genuine forward signal-quality impact is a secondary tiebreaker; blocked natural-history or unsupported-executor work is deferred; every admitted science design must be one-search, one-mutation, no-mining, no-OOS-reuse, multiple-testing protected, replication-required and no-paid-compute-escalation; later ties prefer restrictive abstention-first science",
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "raises_heavy_concurrency": False,
    }

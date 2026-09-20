from pathlib import Path

import pytest

from profitability_learning.contracts import (
    fingerprint,
    verified_executor_implementation,
)
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_quant_science_factory import (
    MASSIVE_VIRTUAL_RESEARCH_CONSTRAINTS,
    MAX_PER_METHOD,
    _scientific_design,
    _strategy_identity,
    build_quant_science_queue,
    verified_strategy_semantic_fingerprint,
)


def _priority(dimension, group, wrong_rate=0.5, independent_samples=30):
    return {
        "dimension": dimension,
        "group": group,
        "samples": independent_samples * 2,
        "independent_samples": independent_samples,
        "wrong_rate": wrong_rate,
        "research_question": f"Can {dimension}={group} support a restrictive challenger?",
        "requires_new_validation": True,
    }


def test_quant_science_factory_predeclares_safe_scientific_design():
    diagnostics = {"research_priorities": [_priority("score_band", "70-79")]}
    queue = build_quant_science_queue(diagnostics)
    assert queue["experiment_count"] == 1
    experiment = queue["experiments"][0]
    design = experiment["science_design"]
    assert design["research_method"] == "selective_abstention_calibration"
    assert design["primary_endpoint"] == "after_cost_selective_precision_on_untouched_oos"
    assert design["predeclared_search_budget"] == 1
    assert design["max_candidate_mutations"] == 1
    assert design["minimum_evaluation_samples"] == 8
    assert design["minimum_actionable_coverage"] == 0.25
    assert design["executor_kind"] == "restrictive_group_abstention_v1"
    assert design["executor_implementation_id"] == (
        "research_adaptive_accuracy._evaluate_frozen_filter@v2-source-bundle"
    )
    assert len(design["executor_implementation_sha256"]) == 64
    assert design["dispatchable_now"] is True
    assert design["parameter_mining_allowed"] is False
    assert design["untouched_oos_reuse_allowed"] is False
    assert design["forward_evidence_pooled_with_oos"] is False
    assert design["multiple_testing_firewall_required"] is True
    assert design["independent_replication_required"] is True
    assert design["genuine_forward_replication_required"] is True
    assert design["duplicate_hypothesis_research_penalty_required"] is True
    assert design["paid_compute_escalation_allowed"] is False
    assert design["idea_generation_counts_as_evidence"] is False
    assert design["abstention_first"] is True
    assert experiment["strategy_fingerprint"] == fingerprint(experiment["strategy"])
    assert experiment["strategy"]["execution_rule"] == design["executor_kind"]
    assert experiment["trade_authority"] is False
    assert experiment["promotion_authority"] is False


def test_stale_executor_registry_identity_fails_closed(monkeypatch):
    candidate = {
        "dimension": "market_regime",
        "group": "TREND",
        "target_horizon": "both",
        "predicted_mechanism": "predeclared mechanism",
        "hypothesis": "predeclared hypothesis",
    }
    candidate["science_design"] = _scientific_design(candidate)
    candidate["strategy"] = _strategy_identity(
        candidate, candidate["science_design"]
    )
    candidate["strategy_fingerprint"] = fingerprint(candidate["strategy"])

    import research_quant_science_factory as factory

    def stale_implementation(_executor):
        raise ValueError("registered executor implementation digest is stale")

    monkeypatch.setattr(
        factory,
        "_verified_executor_implementation",
        stale_implementation,
        raising=False,
    )
    with pytest.raises(ValueError, match="implementation digest is stale"):
        verified_strategy_semantic_fingerprint(candidate)


@pytest.mark.parametrize("dependency_name", ["selective_precision.py", "utils.py"])
def test_transitive_executor_dependency_drift_fails_closed(
    monkeypatch, dependency_name
):
    original_read_text = Path.read_text

    def changed_dependency(path, *args, **kwargs):
        source = original_read_text(path, *args, **kwargs)
        if path.name == dependency_name:
            return source + "\n_TRANSITIVE_EXECUTOR_DRIFT = True\n"
        return source

    monkeypatch.setattr(Path, "read_text", changed_dependency)
    with pytest.raises(ValueError, match="implementation digest is stale"):
        verified_executor_implementation("restrictive_group_abstention_v1")


def test_massive_virtual_scale_never_raises_physical_or_cost_authority():
    queue = build_quant_science_queue({"research_priorities": [_priority("score_band", "70-79")]})
    policy = queue["massive_virtual_research_constraints"]
    assert policy == MASSIVE_VIRTUAL_RESEARCH_CONSTRAINTS
    assert policy["logical_idea_space_unbounded"] is True
    assert policy["physical_heavy_concurrency_may_increase"] is False
    assert policy["paid_compute_escalation_allowed"] is False
    assert policy["monthly_infrastructure_ceiling_usd"] == 30
    assert policy["trade_authority"] is False
    assert policy["promotion_authority"] is False


def test_horizon_calibration_is_design_only_until_executor_exists():
    queue = build_quant_science_queue({"research_priorities": [_priority("horizon", "24h")]})
    design = queue["experiments"][0]["science_design"]
    assert design["dispatchable_now"] is False
    assert design["executor_kind"] == "design_only"
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 0


def test_quant_science_factory_caps_hypothesis_family_breadth():
    diagnostics = {
        "research_priorities": [
            _priority("score_band", f"band-{idx}", wrong_rate=0.9 - idx * 0.01, independent_samples=40)
            for idx in range(MAX_PER_METHOD + 5)
        ]
    }
    queue = build_quant_science_queue(diagnostics)
    assert queue["method_counts"]["selective_abstention_calibration"] == MAX_PER_METHOD
    assert queue["experiment_count"] == MAX_PER_METHOD


def test_scheduler_defers_blocked_natural_history_candidate():
    diagnostics = {
        "research_priorities": [
            _priority("market_regime", "TREND", wrong_rate=0.7, independent_samples=40),
            _priority("score_band", "70-79", wrong_rate=0.5, independent_samples=30),
        ]
    }
    queue = build_quant_science_queue(diagnostics)
    blocked = queue["experiments"][0]
    blocked["evidence_readiness"] = "BLOCKED_NATURAL_HISTORY_ACCUMULATION"
    plan = build_heavy_dispatch_plan(queue)
    assert plan["blocked_candidate_count"] == 1
    assert plan["selected_count"] == 1
    assert plan["selected"][0]["experiment_id"] != blocked["experiment_id"]
    assert plan["selected"][0]["executor_kind"] == "restrictive_group_abstention_v1"
    assert plan["raises_heavy_concurrency"] is False


def test_scheduler_rejects_science_design_that_allows_oos_reuse():
    diagnostics = {"research_priorities": [_priority("score_band", "80-89")]}
    queue = build_quant_science_queue(diagnostics)
    queue["experiments"][0]["science_design"]["untouched_oos_reuse_allowed"] = True
    plan = build_heavy_dispatch_plan(queue)
    assert plan["selected_count"] == 0


def test_scheduler_rejects_massive_scale_safety_regressions():
    diagnostics = {"research_priorities": [_priority("score_band", "80-89", independent_samples=30)]}
    unsafe_fields = {
        "predeclared_search_budget": 2,
        "max_candidate_mutations": 2,
        "multiple_testing_firewall_required": False,
        "independent_replication_required": False,
        "genuine_forward_replication_required": False,
        "duplicate_hypothesis_research_penalty_required": False,
        "paid_compute_escalation_allowed": True,
        "idea_generation_counts_as_evidence": True,
    }
    for field, unsafe_value in unsafe_fields.items():
        queue = build_quant_science_queue(diagnostics)
        queue["experiments"][0]["science_design"][field] = unsafe_value
        assert build_heavy_dispatch_plan(queue)["selected_count"] == 0


def test_scheduler_rejects_too_few_independent_samples_for_science_design():
    queue = build_quant_science_queue({"research_priorities": [_priority("score_band", "thin", independent_samples=7)]})
    assert queue["experiment_count"] == 1
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 0

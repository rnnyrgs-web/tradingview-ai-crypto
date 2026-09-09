from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from continuous_worker_army import WORKERS
from research_artifact import seal_research_payload, verify_research_envelope
from research_experiment_factory import build_experiment_queue
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_learning import learning_diagnostics
from signal_development import (
    ObjectiveError,
    PRIMARY_MISSION,
    PRIMARY_OBJECTIVE_ID,
    build_signal_quality_scorecard,
    load_objective,
    priority_score,
    validate_objective,
    validate_task_contract,
)


def _resolved(horizon, direction, correct, due, *, stage="genuine_forward", regime="trend", liquidity="top15", after_cost=0.1):
    return {
        "horizon": horizon,
        "direction": direction,
        "correct": correct,
        "due_at": due.isoformat(),
        "resolved_at": (due + timedelta(minutes=1)).isoformat(),
        "evidence_stage": stage,
        "market_regime": regime,
        "liquidity_bucket": liquidity,
        "after_cost_return_pct": after_cost,
    }


def test_primary_signal_objective_cannot_be_silently_replaced():
    objective = load_objective()
    assert objective["objective_id"] == PRIMARY_OBJECTIVE_ID
    assert objective["primary_mission"] == PRIMARY_MISSION
    for field, value in (("objective_id", "OTHER"), ("primary_mission", "maximize historical accuracy")):
        bad = copy.deepcopy(objective)
        bad[field] = value
        with pytest.raises(ObjectiveError):
            validate_objective(bad)


def test_canonical_safety_and_acc002_liquidity_blocker_are_fail_closed():
    objective = load_objective()
    inv = objective["hard_invariants"]
    assert inv["monthly_recurring_ceiling_usd"] == 30
    assert inv["increase_heavy_concurrency_for_speed"] is False
    assert inv["automatic_merge"] is False
    assert inv["broker_connected"] is False
    assert inv["reset_paper_evidence"] is False
    assert inv["fabricate_historical_data"] is False
    assert inv["weaken_validation_gates"] is False
    blocker = objective["current_bottleneck"]
    assert blocker["reason"] == "insufficient_supported_liquidity_subsets"
    assert blocker["minimum_subset_coverage"] == 0.8
    assert blocker["lower_requirement_allowed"] is False


def test_every_worker_class_has_explicit_signal_development_path():
    registry = load_objective()["worker_registry"]
    required = {
        "python_research_workers",
        "cross_asset_rank_24h",
        "cross_asset_rank_7d",
        "learning_diagnostics",
        "experiment_factory",
        "heavy_experiment_scheduler",
        "validation_workers",
        "autonomous_cloud_specialist",
        "lead_coordination",
        "operational_security_workers",
    }
    assert set(registry) == required
    assert all(row["purpose"] and row["signal_path"] for row in registry.values())
    assert "do not claim alpha" in registry["operational_security_workers"]["purpose"]


def test_every_current_worker_army_process_is_explicitly_bound_to_objective():
    bindings = json.loads(Path("orchestration/signal_worker_bindings.json").read_text(encoding="utf-8"))
    assert bindings["objective_id"] == PRIMARY_OBJECTIVE_ID
    configured = {spec.name for spec in WORKERS}
    assert configured == set(bindings["worker_army"])
    registry = load_objective()["worker_registry"]
    for row in bindings["worker_army"].values():
        assert row["class"] in registry
        assert row["signal_role"]
    assert bindings["binding_policy"]["all_outputs_must_trace_to_objective"] is True
    assert bindings["binding_policy"]["operational_security_may_claim_alpha"] is False
    assert bindings["binding_policy"]["cosmetic_work_may_displace_signal_research"] is False


def test_ai_specialists_and_lead_have_explicit_signal_paths():
    bindings = json.loads(Path("orchestration/signal_worker_bindings.json").read_text(encoding="utf-8"))
    required = {
        "autonomous-cloud-data-market",
        "quant-research",
        "signal-accuracy",
        "data-market",
        "regime-selection",
        "execution-microstructure",
        "production-risk",
        "testing-security",
        "lead-integrator",
    }
    assert set(bindings["ai_and_coordination"]) == required
    assert "no alpha claim" in bindings["ai_and_coordination"]["testing-security"]["signal_role"]


def test_task_contract_requires_falsifiable_measurable_fields():
    diagnostics = {
        "research_priorities": [{
            "dimension": "direction",
            "group": "BUY",
            "research_question": "Can a restrictive condition reduce BUY false positives?",
            "requires_new_validation": True,
            "samples": 30,
            "independent_samples": 20,
            "wrong_rate": 0.4,
            "target_horizon": "24h",
        }]
    }
    queue = build_experiment_queue(diagnostics, {})
    experiment = queue["experiments"][0]
    validate_task_contract(experiment)
    assert experiment["evidence_conclusion"] == "unresolved"
    assert experiment["result"] is None
    assert experiment["falsification_criteria"]
    assert experiment["independent_sample_requirements"]
    bad = dict(experiment)
    bad.pop("falsification_criteria")
    with pytest.raises(ObjectiveError):
        validate_task_contract(bad)


def test_priority_formula_prefers_high_signal_information_value_per_cost():
    high = priority_score(
        expected_genuine_signal_quality_impact=1.0,
        expected_information_falsification_value=1.0,
        probability_actionable_evidence=0.95,
        compute_api_cost_units=0.5,
    )
    cosmetic = priority_score(
        expected_genuine_signal_quality_impact=0.1,
        expected_information_falsification_value=0.2,
        probability_actionable_evidence=0.9,
        compute_api_cost_units=0.5,
    )
    assert high > cosmetic


def test_scorecard_counts_only_non_overlapping_full_horizon_evidence():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = [
        _resolved("24h", "BUY", True, start + timedelta(hours=24), after_cost=0.4),
        _resolved("24h", "BUY", False, start + timedelta(hours=25), after_cost=-0.2),
        _resolved("24h", "SELL", True, start + timedelta(hours=48), after_cost=0.3),
        _resolved("7d", "BUY", True, start + timedelta(days=7), after_cost=1.0),
        _resolved("7d", "SELL", False, start + timedelta(days=14), after_cost=-0.5),
    ]
    scorecard = build_signal_quality_scorecard(rows)
    h24 = scorecard["horizons"]["24h"]
    assert h24["independent_observation_count"] == 2
    assert h24["buy"]["independent_observations"] == 1
    assert h24["sell"]["independent_observations"] == 1
    assert h24["buy"]["wilson_95"][0] is not None
    assert scorecard["historical_oos_vs_genuine_forward"].startswith("must remain separated")


def test_resolved_errors_feed_hypotheses_and_bounded_heavy_selection():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(14):
        rows.append(_resolved("24h", "BUY", i % 3 == 0, start + timedelta(days=i + 1), after_cost=-0.1))
    diagnostics = learning_diagnostics(rows, minimum_samples=12)
    assert diagnostics["objective"]["objective_id"] == PRIMARY_OBJECTIVE_ID
    assert diagnostics["research_priorities"]
    queue = build_experiment_queue(diagnostics, {})
    assert queue["objective"]["objective_id"] == PRIMARY_OBJECTIVE_ID
    plan = build_heavy_dispatch_plan(queue)
    assert plan["heavy_slot_limit"] == 1
    assert plan["selected_count"] <= 1
    assert plan["raises_heavy_concurrency"] is False


def test_all_sealed_research_artifacts_are_bound_to_primary_objective():
    envelope = seal_research_payload({"results": []})
    assert envelope["payload"]["signal_development_objective"] == PRIMARY_OBJECTIVE_ID
    assert envelope["payload"]["primary_signal_development_mission"] == PRIMARY_MISSION
    assert verify_research_envelope(envelope) is True
    with pytest.raises(RuntimeError):
        seal_research_payload({"signal_development_objective": "OTHER"})


def test_autonomous_cloud_runner_is_bound_to_same_objective_and_acc002_first_priority():
    config = json.loads(Path("orchestration/autonomous_specialist_runner.json").read_text(encoding="utf-8"))
    assert config["objective_id"] == PRIMARY_OBJECTIVE_ID
    assert config["primary_mission"] == PRIMARY_MISSION
    assert config["policy"]["max_concurrent_agent_runs"] == 1
    assert config["budget"]["project_monthly_ceiling_usd"] == 30.0
    assert "ACC-002" in config["roles"]["data-market"]["mission"]
    assert "0.80" in config["roles"]["data-market"]["mission"]

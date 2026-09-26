from __future__ import annotations

import json
import copy
from pathlib import Path

import pytest

from agents.autonomous_cloud_runner import PolicyError, load_config, validate_config
from continuous_worker_army import WORKERS, focused_worker_specs, load_strategy_discovery_queue
from signal_development import ObjectiveError, load_objective, validate_objective
from orchestration.specialist_coordination import validate_state


ROOT = Path(__file__).resolve().parents[1]


def _load(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_canonical_objective_focuses_deep_work_on_one_strategy_candidate():
    objective = load_objective()
    focus = objective["single_strategy_focus"]

    assert focus["enabled"] is True
    assert focus["max_active_deep_candidates"] == 1
    assert focus["broad_unrelated_research"] == "DEPRIORITIZED"
    assert focus["success_state"] == "VALIDATED_RESEARCH_CANDIDATE"
    assert focus["selection_screen_workers"]
    assert "positive_after_cost_expectancy" in focus["required_evidence"]
    assert "untouched_oos" in focus["required_evidence"]
    assert "genuine_forward_paper_validation" in focus["required_evidence"]
    assert focus["real_money_trading_authority"] is False
    assert focus["lifecycle_phase"] == "SELECTION"
    assert focus["active_candidate"] is None


def test_every_persistent_ai_engine_inherits_single_strategy_focus():
    paths = (
        "orchestration/autonomous_specialist_runner.json",
        "orchestration/autonomous_specialist_runner_claude.json",
        "orchestration/autonomous_specialist_runner_claude_code.json",
    )
    for path in paths:
        config = _load(path)
        assert config["objective_id"] == "UNIVERSAL_SIGNAL_DEVELOPMENT_V1"
        assert config["policy"]["single_strategy_focus"] is True
        assert config["policy"]["max_active_deep_strategy_candidates"] == 1
        assert config["policy"]["broad_unrelated_research"] == "DEPRIORITIZED"
        assert config["policy"]["single_strategy_lifecycle_phase"] == "SELECTION"
        assert config["policy"]["active_strategy_candidate"] is None
        mission_text = " ".join(
            [config["primary_mission"]]
            + [role["mission"] for role in config["roles"].values()]
        ).lower()
        assert "one strategy" in mission_text
        assert "after-cost" in mission_text
        assert config["policy"]["trade_authority"] is False
        assert config["policy"]["broker_connected"] is False


def test_worker_fleet_routes_to_one_candidate_without_claiming_alpha():
    bindings = _load("orchestration/signal_worker_bindings.json")
    policy = bindings["binding_policy"]

    assert policy["single_strategy_focus"] is True
    assert policy["max_active_deep_strategy_candidates"] == 1
    assert policy["broad_unrelated_research"] == "DEPRIORITIZED"
    assert policy["single_strategy_lifecycle_phase"] == "SELECTION"
    assert policy["active_strategy_candidate"] is None
    assert all(row["signal_role"] for row in bindings["worker_army"].values())
    assert "one strategy" in bindings["ai_and_coordination"]["lead-integrator"]["signal_role"].lower()
    assert policy["operational_security_may_claim_alpha"] is False


def test_selection_phase_safe_idles_candidate_heavy_workers_without_active_queue_candidate():
    objective = load_objective()
    discovery_queue = load_strategy_discovery_queue()
    assert objective["single_strategy_focus"]["active_candidate"] is None
    assert discovery_queue["active_deep_candidate"] is None

    selected = focused_worker_specs(WORKERS, objective, discovery_queue)
    selected_names = {worker.name for worker in selected}

    assert selected_names == {"learning-diagnostics", "experiment-factory"}
    assert all(worker.compute_class == "lightweight" for worker in selected)
    assert "cross-asset-rank-24h" not in selected_names


def test_active_candidate_allows_only_its_declared_deep_workers():
    objective = load_objective()
    objective["single_strategy_focus"]["lifecycle_phase"] = "DEEP_VALIDATION"
    objective["single_strategy_focus"]["active_candidate"] = {
        "fingerprint_id": "TEST-CANDIDATE-V1",
        "deep_worker_contracts": {
            "major-btc": {"strategy_family": "trend"},
        },
    }
    discovery_queue = load_strategy_discovery_queue()
    discovery_queue["lifecycle_phase"] = "DEEP_VALIDATION"
    discovery_queue["active_deep_candidate"] = "TEST-CANDIDATE-V1"
    selected = focused_worker_specs(WORKERS, objective, discovery_queue)
    heavy = [worker for worker in selected if worker.compute_class == "heavy"]
    assert [worker.name for worker in heavy] == ["major-btc"]
    assert heavy[0].env["SINGLE_STRATEGY_DEEP_MODE"] == "1"
    assert heavy[0].env["ACTIVE_STRATEGY_FINGERPRINT"] == "TEST-CANDIDATE-V1"
    assert heavy[0].env["ACTIVE_STRATEGY_FAMILY"] == "trend"


@pytest.mark.parametrize("field,value", [
    ("single_strategy_focus", False),
    ("max_active_deep_strategy_candidates", 2),
])
def test_runner_rejects_single_strategy_policy_drift(field, value):
    config = copy.deepcopy(load_config())
    config["policy"][field] = value
    with pytest.raises(PolicyError):
        validate_config(config)


def test_objective_rejects_weakened_focus_contract():
    for field, value in (("broad_unrelated_research", "PRIORITIZED"), ("success_state", "BACKTEST_ONLY")):
        objective = copy.deepcopy(load_objective())
        objective["single_strategy_focus"][field] = value
        with pytest.raises(ObjectiveError):
            validate_objective(objective)


def test_specialist_coordination_persists_the_same_focus_and_gates():
    coordination = _load("orchestration/specialist_coordination.json")
    policy = coordination["policy"]

    assert "one strategy" in coordination["objective"].lower()
    assert policy["single_strategy_focus"] is True
    assert policy["max_active_deep_strategy_candidates"] == 1
    assert policy["broad_unrelated_research"] == "DEPRIORITIZED"
    assert policy["broker_connected"] is False
    assert "untouched_oos" in policy["required_validation"]


def test_coordination_rejects_multiple_deep_candidate_fingerprints():
    coordination = _load("orchestration/specialist_coordination.json")
    ready = [task for task in coordination["tasks"] if task["status"] == "READY"][:2]
    for index, task in enumerate(ready):
        task["work_mode"] = "DEEP"
        task["fingerprint_id"] = f"CANDIDATE-{index}"
    with pytest.raises(RuntimeError, match="one active deep candidate"):
        validate_state(coordination)


def test_coordination_rejects_deep_work_during_selection():
    coordination = _load("orchestration/specialist_coordination.json")
    task = next(task for task in coordination["tasks"] if task["status"] == "READY")
    task["work_mode"] = "DEEP"
    task["fingerprint_id"] = "TEST-CANDIDATE-V1"
    with pytest.raises(RuntimeError, match="SELECTION"):
        validate_state(coordination)

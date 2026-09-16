import copy

import pytest

from orchestration.specialist_coordination import load_state, validate_state


def _active_tasks(state):
    return [
        task for task in state["tasks"]
        if task.get("status") in {"READY", "IN_PROGRESS", "PR_OPEN"}
    ]


def test_only_one_active_change_lane_is_allowed_across_the_team():
    state = load_state()
    bad = copy.deepcopy(state)
    active = _active_tasks(bad)
    assert len(active) >= 2
    active[0]["research_lane"] = "CHANGE"
    active[0]["strategy_mutation_authority"] = True
    active[1]["research_lane"] = "CHANGE"
    active[1]["strategy_mutation_authority"] = True
    with pytest.raises(RuntimeError, match="one active CHANGE lane"):
        validate_state(bad)


def test_review_falsification_data_and_evidence_lanes_cannot_mutate_strategy():
    state = load_state()
    bad = copy.deepcopy(state)
    active = _active_tasks(bad)
    active[0]["research_lane"] = "FALSIFICATION"
    active[0]["strategy_mutation_authority"] = True
    with pytest.raises(RuntimeError, match="non-CHANGE lane cannot mutate strategy"):
        validate_state(bad)


def test_support_lanes_can_run_in_parallel_without_mutation_authority():
    state = load_state()
    safe = copy.deepcopy(state)
    lanes = ["REVIEW", "FALSIFICATION", "DATA_CERTIFICATION", "EVIDENCE_COLLECTION"]
    for index, task in enumerate(_active_tasks(safe)):
        task["research_lane"] = lanes[index % len(lanes)]
        task["strategy_mutation_authority"] = False
    validate_state(safe)

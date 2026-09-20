from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

from agents.autonomous_cloud_runner import (
    CONFIG_PATH,
    PolicyError,
    default_state,
    highest_ready_task,
    load_config,
    load_coordination,
    plan_decision,
)


def _owner_matching_ready_task(coordination: dict, eligible_engines: list[str]) -> dict:
    source = next(
        task for task in coordination["tasks"]
        if task.get("owner") == "data-market"
    )
    task = copy.deepcopy(source)
    task.update(
        {
            "id": "COORD-ENGINE-ELIGIBILITY-REGRESSION",
            "priority": 0,
            "status": "READY",
            "blockers": [],
            "issue": None,
            "pr": None,
            "eligible_engines": eligible_engines,
        }
    )
    task.pop("completion_evidence", None)
    return task


def test_openai_runner_has_explicit_chatgpt_engine_identity():
    config = load_config()
    assert config["engine"] == "chatgpt"


@pytest.mark.parametrize("engine", [None, "unknown", "claude"])
def test_openai_runner_rejects_missing_or_wrong_engine_at_load_time(tmp_path, engine):
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if engine is None:
        config.pop("engine")
    else:
        config["engine"] = engine
    path = tmp_path / CONFIG_PATH.name
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(PolicyError, match="engine"):
        load_config(path)


@pytest.mark.parametrize("engine", [None, "", "unknown"])
def test_task_selection_rejects_missing_or_unknown_engine(engine):
    config = copy.deepcopy(load_config())
    if engine is None:
        config.pop("engine")
    else:
        config["engine"] = engine

    with pytest.raises(PolicyError, match="engine"):
        highest_ready_task(config, load_coordination())


def test_openai_runner_cannot_claim_owner_matching_task_excluding_chatgpt():
    config = load_config()
    coordination = copy.deepcopy(load_coordination())
    task = _owner_matching_ready_task(coordination, ["human", "claude", "claude-code"])
    coordination["tasks"].append(task)

    assert highest_ready_task(config, coordination) is None

    decision = plan_decision(
        config,
        coordination,
        default_state(),
        "a" * 40,
        datetime(2026, 9, 20, 3, 15, tzinfo=timezone.utc),
    )
    assert decision.run is False
    assert decision.reason == "NO_READY_AUTONOMOUS_TASK"

    task["eligible_engines"] = ["chatgpt"]
    assert highest_ready_task(config, coordination)["id"] == task["id"]

from __future__ import annotations

import copy

from agents.autonomous_cloud_runner import highest_ready_task, load_config, load_coordination


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


def test_openai_runner_cannot_claim_owner_matching_task_excluding_chatgpt():
    config = load_config()
    coordination = copy.deepcopy(load_coordination())
    task = _owner_matching_ready_task(coordination, ["human", "claude", "claude-code"])
    coordination["tasks"].append(task)

    assert highest_ready_task(config, coordination) is None

    task["eligible_engines"] = ["chatgpt"]
    assert highest_ready_task(config, coordination)["id"] == task["id"]

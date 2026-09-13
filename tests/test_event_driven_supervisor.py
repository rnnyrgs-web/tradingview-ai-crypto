import json
from pathlib import Path

from agents.supervisor_snapshot import build_snapshot, load_backlog, ready_items


def test_priority_backlog_is_ordered_and_fail_closed():
    backlog = load_backlog()
    assert backlog["policy"]["max_change_tasks_per_cycle"] == 1
    assert backlog["policy"]["live_promotion_from_backlog"] is False
    assert backlog["policy"]["insufficient_evidence"] == "WAIT_RESEARCH_ONLY"
    ready = ready_items(backlog)
    # READY is intentionally a dynamic subset: scientifically blocked tasks must
    # be allowed to leave the runnable queue without making the supervisor test
    # demand that they be re-enabled merely to satisfy an inventory count.
    assert ready
    assert [item["priority"] for item in ready] == sorted(item["priority"] for item in ready)
    assert all(item["owner"] for item in ready)
    assert all(item["status"] == "READY" for item in ready)


def test_supervisor_snapshot_is_compact_and_contains_handoff_and_queue(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    snapshot = build_snapshot()
    ready = ready_items(load_backlog())
    assert snapshot["event"]["name"] == "schedule"
    assert ready
    assert snapshot["highest_ready"] == ready[0]["id"]
    assert "EXACT NEXT STEP" in snapshot["exact_next_step"]
    assert "SAFETY INVARIANTS" in snapshot["safety_invariants"]
    assert len(json.dumps(snapshot)) < 20000


def test_legacy_autonomous_swarm_is_manual_only_and_cloud_runner_is_scheduled():
    legacy = Path(".github/workflows/autonomous_agents.yml").read_text(encoding="utf-8")
    cloud = Path(".github/workflows/autonomous_cloud_specialist.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in legacy
    assert "workflow_run:" not in legacy
    assert "schedule:" not in legacy
    assert 'cron: "17 * * * *"' not in legacy
    assert "max-parallel: 14" in legacy
    assert "workflow_dispatch:" in cloud
    assert 'cron: "41 * * * *"' in cloud
    assert "max-parallel" not in cloud
    assert "autonomous_cloud_runner.py plan" in cloud
    assert "runner_state.json" in cloud


def test_backlog_cannot_directly_authorize_live_promotion():
    backlog = json.loads(Path("orchestration/priority_backlog.json").read_text(encoding="utf-8"))
    serialized = json.dumps(backlog).upper()
    assert backlog["policy"]["live_promotion_from_backlog"] is False
    assert "WAIT_RESEARCH_ONLY" in serialized

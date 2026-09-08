import json
from pathlib import Path

from agents.supervisor_snapshot import build_snapshot, load_backlog, ready_items


def test_priority_backlog_is_ordered_and_fail_closed():
    backlog = load_backlog()
    assert backlog["policy"]["max_change_tasks_per_cycle"] == 1
    assert backlog["policy"]["live_promotion_from_backlog"] is False
    assert backlog["policy"]["insufficient_evidence"] == "WAIT_RESEARCH_ONLY"
    ready = ready_items(backlog)
    assert len(ready) >= 7
    assert [item["priority"] for item in ready] == sorted(item["priority"] for item in ready)
    assert ready[0]["id"] == "ACC-001"
    assert all(item["owner"] for item in ready)


def test_supervisor_snapshot_is_compact_and_contains_handoff_and_queue(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    snapshot = build_snapshot()
    assert snapshot["event"]["name"] == "schedule"
    assert snapshot["highest_ready"] == "ACC-001"
    assert "EXACT NEXT STEP" in snapshot["exact_next_step"]
    assert "SAFETY INVARIANTS" in snapshot["safety_invariants"]
    assert len(json.dumps(snapshot)) < 20000


def test_autonomous_workflow_is_hourly_manual_and_quota_safe():
    workflow = Path(".github/workflows/autonomous_agents.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "workflow_run:" not in workflow
    assert 'cron: "17 * * * *"' in workflow
    assert "safely skipping this cycle" in workflow
    assert "active_roles=[]" in workflow
    assert "python agents/supervisor_snapshot.py" in workflow
    assert "orchestration/" in workflow
    assert "max-parallel: 14" in workflow


def test_backlog_cannot_directly_authorize_live_promotion():
    backlog = json.loads(Path("orchestration/priority_backlog.json").read_text(encoding="utf-8"))
    serialized = json.dumps(backlog).upper()
    assert backlog["policy"]["live_promotion_from_backlog"] is False
    assert "WAIT_RESEARCH_ONLY" in serialized

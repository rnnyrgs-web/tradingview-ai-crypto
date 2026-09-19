import json

from orchestration.coordination_overrides import ROOT, apply_coordination_overrides
from orchestration.specialist_coordination import validate_state


def _tasks_by_id(payload):
    return {task["id"]: task for task in payload["tasks"]}


def test_lead_reconciliation_closes_stale_data_task_and_routes_safe_followup():
    coordination_path = ROOT / "orchestration" / "specialist_coordination.json"
    base = json.loads(coordination_path.read_text(encoding="utf-8"))
    resolved = apply_coordination_overrides(base)
    validate_state(resolved)
    tasks = _tasks_by_id(resolved)

    assert tasks["COORD-DISC-DATA-003"]["status"] == "DONE"
    assert tasks["COORD-DISC-DATA-003"]["pr"] == 423
    assert tasks["COORD-DISC-DATA-003"]["completion_evidence"]["outcomes_inspected"] is False
    assert tasks["COORD-DISC-DATA-003"]["completion_evidence"]["untouched_oos_opened"] is False

    # Independent pre-outcome design/falsification work stays actionable, while the
    # data lane resolves the remaining timestamp/coverage contract without opening OOS.
    assert tasks["COORD-DISC-QUANT-003"]["status"] == "READY"
    assert tasks["COORD-DISC-DATA-004"]["status"] == "READY"
    assert tasks["COORD-DISC-DATA-004"]["blockers"] == []
    assert tasks["COORD-DISC-DATA-004"]["fingerprint_id"] == "DISC-SQUEEZE-RETENTION-001-v1"
    assert tasks["COORD-DISC-DATA-004"]["completion_rule"].startswith("Either return one frozen")
    assert "Do not inspect strategy returns or untouched OOS" in tasks["COORD-DISC-DATA-004"]["completion_rule"]

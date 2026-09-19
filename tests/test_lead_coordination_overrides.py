import json

from orchestration.coordination_overrides import apply_coordination_overrides
from orchestration.specialist_coordination import COORDINATION_PATH, validate_state


def _tasks_by_id(payload):
    return {task["id"]: task for task in payload["tasks"]}


def test_lead_reconciliation_stops_stale_squeeze_data_execution():
    base = json.loads(COORDINATION_PATH.read_text(encoding="utf-8"))
    resolved = apply_coordination_overrides(base)
    validate_state(resolved)
    tasks = _tasks_by_id(resolved)

    assert tasks["COORD-DISC-DATA-003"]["status"] == "DONE"
    assert tasks["COORD-DISC-DATA-003"]["pr"] == 423
    assert tasks["COORD-DISC-DATA-003"]["completion_evidence"]["outcomes_inspected"] is False
    assert tasks["COORD-DISC-DATA-003"]["completion_evidence"]["untouched_oos_opened"] is False

    assert tasks["COORD-DISC-QUANT-003"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-DATA-004"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-DATA-004"]["fingerprint_id"] == "DISC-SQUEEZE-RETENTION-001-v1"
    assert tasks["COORD-DISC-DATA-004"]["completion_rule"].startswith("Either return one frozen")

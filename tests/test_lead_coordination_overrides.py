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

    # The unavailable source closes candidate-specific work without turning a
    # data-contract failure into a strategy rejection. The successor task is
    # now historical DONE evidence for the independently merged rejection.
    assert tasks["COORD-DISC-QUANT-003"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-VAL-003"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-TEST-003"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-DATA-004"]["status"] == "DONE"
    assert tasks["COORD-DISC-DATA-004"]["blockers"] == []
    assert tasks["COORD-DISC-DATA-004"]["fingerprint_id"] == "DISC-SQUEEZE-RETENTION-001-v1"
    assert tasks["COORD-DISC-DATA-004"]["completion_rule"].startswith("Either return one frozen")
    assert "Do not inspect strategy returns or untouched OOS" in tasks["COORD-DISC-DATA-004"]["completion_rule"]
    assert tasks["COORD-DISC-DATA-004"]["completion_evidence"]["untouched_oos_opened"] is False
    assert tasks["COORD-DISC-QUANT-004"]["status"] == "DONE"
    assert tasks["COORD-DISC-QUANT-004"]["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert tasks["COORD-DISC-QUANT-004"]["completion_evidence"]["decision"] == "REJECTED_PRE_OOS"
    assert tasks["COORD-DISC-QUANT-004"]["completion_evidence"]["untouched_oos_opened"] is False

    primitive = tasks["COORD-MI-CAUSAL-001"]
    assert primitive["status"] == "DONE"
    assert primitive["owner"] == "quant-research"
    assert primitive["issue"] == 451
    assert primitive["pr"] == 454
    assert primitive["blockers"] == []
    evidence = primitive["completion_evidence"]
    assert evidence["status"] == "PERSISTENT_CAUSAL_MEMORY_PRIMITIVE_INTEGRATED"
    assert evidence["exact_head_sha"] == "8da3ff1d212d28cfd9f04521c7ab7b5ec5a4d8e3"
    assert evidence["merge_sha"] == "dbc5e80c5c664863df645689dcd6df418db8194f"
    assert evidence["exact_head_security_and_reliability_run"] == 35465434613
    assert evidence["post_merge_security_and_reliability_run"] == 35467932500
    assert evidence["phase_2_complete"] is False
    assert evidence["broker_or_live_authority"] is False
    assert primitive["next_task"] == "COORD-MI-CAUSAL-002"

    runtime = tasks["COORD-MI-CAUSAL-002"]
    assert runtime["status"] == "DONE"
    assert runtime["owner"] == "quant-research"
    assert runtime["issue"] == 451
    assert runtime["pr"] == 460
    assert runtime["blockers"] == []
    assert runtime["dependencies"] == ["COORD-MI-CAUSAL-001"]
    requirements = " ".join(runtime["evidence_required"]).lower()
    assert "actual autonomous money intelligence runtime" in requirements
    assert "big-move and strategy-component mission generation/ranking" in requirements
    assert "unsupported narrative-only claims cannot affect" in requirements
    assert "rejected exact strategy fingerprints remain ineligible" in requirements
    assert "no oos/forward opening, broker/trade/promotion authority" in requirements
    assert "exact-deployed-sha runtime acceptance" in requirements
    runtime_evidence = runtime["completion_evidence"]
    assert runtime_evidence["accepted_main_sha"] == "c1737bd4b3340a9073bce64f9f9143f8a0bc03f8"
    assert runtime_evidence["causal_runtime_acceptance_run"] == 35484292758
    assert runtime_evidence["canonical_rejected_id_veto"] is True
    assert runtime_evidence["phase_2_complete"] is True

    adversarial = tasks["COORD-ARCH-ADVERSARIAL-001"]
    assert adversarial["status"] == "READY"
    assert adversarial["owner"] == "testing-security"
    assert adversarial["branch"] == "agent/testing-security"
    assert adversarial["issue"] == 462
    assert adversarial["pr"] is None
    assert adversarial["dependencies"] == ["COORD-MI-CAUSAL-002"]

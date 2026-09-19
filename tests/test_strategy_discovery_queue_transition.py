import json
from pathlib import Path

from strategy_discovery_supervisor import load_queue, snapshot


QUEUE = Path("orchestration/strategy_discovery_queue.json")
EVIDENCE = Path("orchestration/evidence/disc_residual_momentum_001_20260919.json")


def test_residual_negative_evidence_pivots_next_screen_without_terminal_rejection():
    queue = load_queue(QUEUE)
    state = snapshot(queue)

    residual = next(row for row in queue["candidates"] if row["fingerprint_id"] == "DISC-RESIDUAL-MOMENTUM-001-v1")
    assert residual["stage"] == "DEPRIORITIZED_EVIDENCE_LIMITED"
    assert residual["evidence_ref"] == EVIDENCE.as_posix()
    assert residual["blocker"]

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["screen_status"] == "EXPLORATORY_PRE_OOS_FAIL_SURVIVORSHIP_UNVERIFIED"
    assert evidence["selection"]["economic_pre_oos_pass"] is False
    assert evidence["selection"]["eligible_for_deep_freeze"] is False
    assert evidence["selection"]["terminal_rejection_authorized"] is False
    assert evidence["selection"]["untouched_oos_opened"] is False
    assert evidence["point_in_time_universe"]["verified"] is False

    assert state["active_deep_candidate"] is None
    assert state["next_action"]["action"] == "RUN_CHEAP_DETERMINISTIC_SCREEN"
    assert state["next_action"]["fingerprint_id"] == "DISC-VOL-BREAKOUT-001-v1"
    assert all(row["fingerprint_id"] != "DISC-RESIDUAL-MOMENTUM-001-v1" for row in state["ranked_cheap_screens"])

from pathlib import Path

import pytest

from orchestration.rejected_fingerprints import is_rejected_fingerprint, load_rejected_fingerprints
from strategy_discovery_supervisor import load_queue, ranked_screens, snapshot, validate_queue


def test_acc002_is_durably_rejected():
    entries = load_rejected_fingerprints()
    assert is_rejected_fingerprint("ACC-002", entries)
    record = next(row for row in entries if row["fingerprint_id"] == "ACC-002")
    assert record["rejection_evidence"]["eligible_candidate_count"] == 0
    assert record["rejection_evidence"]["untouched_oos_status"] == "LOCKED_UNTOUCHED_OOS"
    assert record["do_not_resubmit_same_fingerprint"] is True


def test_discovery_queue_is_valid_and_research_only():
    payload = load_queue()
    state = snapshot(payload)
    assert payload["max_active_deep_candidates"] == 1
    assert state["active_deep_candidate"] is None
    assert state["research_only"] is True
    assert state["trade_authority"] is False
    assert state["broker_connected"] is False


def test_supervisor_ranks_a_cheap_screen_without_opening_oos():
    payload = load_queue()
    ranked = ranked_screens(payload)
    assert ranked
    assert all(row["work_mode"] == "CHEAP_SCREEN" for row in ranked)
    state = snapshot(payload)
    assert state["next_action"]["action"] == "RUN_CHEAP_DETERMINISTIC_SCREEN"
    assert state["active_deep_candidate"] is None


def test_playbit_lane_is_dedicated_and_blocked_until_exact_source_is_pinned():
    payload = load_queue()
    row = next(row for row in payload["candidates"] if row["family"] == "frizz_playbit_ema")
    assert row["source_fingerprint_required"] is True
    assert row["stage"] == "BLOCKED_SOURCE_FINGERPRINT"
    assert row["blocker"]
    assert "FFRIZZ" in row["blocker"]


def test_big_move_and_money_intelligence_continue_as_independent_generators():
    state = snapshot(load_queue())
    families = {row["family"] for row in state["independent_generators"]}
    assert {"big_move_intelligence", "money_intelligence"} <= families


def test_rejected_fingerprint_cannot_be_requeued():
    payload = load_queue()
    payload["candidates"][0]["fingerprint_id"] = "ACC-002"
    with pytest.raises(RuntimeError, match="rejected fingerprint"):
        validate_queue(payload)


def test_more_than_one_deep_candidate_fails_closed():
    payload = load_queue()
    payload["candidates"][0]["stage"] = "DEEP_VALIDATION"
    payload["candidates"][0]["work_mode"] = "DEEP"
    payload["candidates"][1]["stage"] = "DEEP_VALIDATION"
    payload["candidates"][1]["work_mode"] = "DEEP"
    payload["active_deep_candidate"] = {
        "fingerprint_id": payload["candidates"][0]["fingerprint_id"]
    }
    with pytest.raises(RuntimeError, match="only one strategy"):
        validate_queue(payload)

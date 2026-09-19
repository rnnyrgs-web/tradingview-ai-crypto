"""Adversarial public-boundary tests; no market data or strategy outcomes."""
import copy

import pytest

from strategy_discovery_supervisor import (
    load_queue, ranked_screens, snapshot, validate_queue,
)


def example_queue():
    """Synthetic inputs, not a claim about any real candidate's readiness."""
    candidate = {
        "hypothesis_id": "TEST-BOUNDARY",
        "fingerprint_id": "TEST-BOUNDARY-v1",
        "family": "synthetic_test",
        "lane": "cheap_screen",
        "stage": "CHEAP_SCREEN_READY",
        "work_mode": "CHEAP_SCREEN",
        "economic_mechanism": "Synthetic boundary fixture only",
        "hypothesis": "Synthetic boundary fixture only",
        "target_markets": ["synthetic"],
        "target_timeframes": ["1h"],
        "source_fingerprint_required": False,
        "blocker": None,
        "expected_profitability_impact": 0.5,
        "expected_information_gain": 0.5,
        "falsification_value": 0.5,
        "sample_readiness": 0.5,
        "compute_cost": 0.5,
        "validation_requirements": ["synthetic_test_only"],
    }
    generators = []
    for family in ("big_move_intelligence", "money_intelligence"):
        generator = copy.deepcopy(candidate)
        generator.update(hypothesis_id=f"TEST-{family}",
                         fingerprint_id=f"TEST-{family}-v1", family=family,
                         stage="INDEPENDENT_GENERATOR", lane="hypothesis_generator")
        generators.append(generator)
    return {
        "schema_version": 1, "objective": "Synthetic boundary test",
        "lifecycle_phase": "SELECTION", "active_deep_candidate": None,
        "max_active_deep_candidates": 1,
        "policy": {
            "research_only": True, "trade_authority": False,
            "broker_connected": False,
            "untouched_oos_requires_frozen_selection_pass": True,
            "rejected_fingerprints_are_terminal_without_new_hypothesis": True,
            "no_paid_api_required_for_supervisor": True,
        },
        "candidates": [candidate, *generators],
    }


@pytest.mark.parametrize("boundary", [validate_queue, ranked_screens, snapshot])
@pytest.mark.parametrize("field,wanted", [
    ("research_only", True),
    ("trade_authority", False),
    ("broker_connected", False),
    ("untouched_oos_requires_frozen_selection_pass", True),
    ("rejected_fingerprints_are_terminal_without_new_hypothesis", True),
    ("no_paid_api_required_for_supervisor", True),
])
@pytest.mark.parametrize("mutation", ["missing", "opposite", "string", "integer"])
def test_every_public_boundary_rejects_weakened_or_ambiguous_policy(
    boundary, field, wanted, mutation,
):
    payload = example_queue()
    if mutation == "missing":
        del payload["policy"][field]
    else:
        payload["policy"][field] = {
            "opposite": not wanted, "string": str(wanted), "integer": int(wanted),
        }[mutation]
    with pytest.raises(RuntimeError):
        boundary(payload)


@pytest.mark.parametrize("boundary", [validate_queue, ranked_screens, snapshot])
@pytest.mark.parametrize("limit", [True, "1", 1.0, 1.5, 2, 0, None])
def test_deep_capacity_does_not_silently_coerce_invalid_limit(boundary, limit):
    payload = example_queue()
    payload["max_active_deep_candidates"] = limit
    with pytest.raises(RuntimeError, match="exactly one"):
        boundary(payload)


@pytest.mark.parametrize("boundary", [ranked_screens, snapshot])
def test_rejected_fingerprint_cannot_reenter_through_direct_boundary(boundary):
    payload = example_queue()
    selected = next(r for r in payload["candidates"] if r["stage"] == "CHEAP_SCREEN_READY")
    selected["fingerprint_id"] = "DISC-LIQUIDITY-MEANREV-001-v1"
    with pytest.raises(RuntimeError, match="rejected fingerprint"):
        boundary(payload)


@pytest.mark.parametrize("boundary", [ranked_screens, snapshot])
def test_multiple_deep_candidates_cannot_bypass_loader(boundary):
    payload = example_queue()
    for row in payload["candidates"][:2]:
        row.update(stage="DEEP_VALIDATION", work_mode="DEEP")
    payload["active_deep_candidate"] = {
        "fingerprint_id": payload["candidates"][0]["fingerprint_id"],
    }
    with pytest.raises(RuntimeError, match="only one strategy"):
        boundary(payload)


def test_valid_public_reads_preserve_input_and_do_not_grant_authority():
    payload = example_queue()
    before = copy.deepcopy(payload)
    result = snapshot(payload)
    assert result["next_action"]["action"] == "RUN_CHEAP_DETERMINISTIC_SCREEN"
    assert result["active_deep_candidate"] is None
    assert result["research_only"] is True
    assert result["broker_connected"] is False
    assert result["trade_authority"] is False
    assert payload == before


def test_wait_does_not_invent_candidate_or_block_independent_generators():
    payload = example_queue()
    for row in payload["candidates"]:
        if row["stage"] == "CHEAP_SCREEN_READY":
            row["blocker"] = "publication chronology not verified"
    result = snapshot(payload)
    assert result["next_action"] is None
    assert result["ranked_cheap_screens"] == []
    assert {row["family"] for row in result["independent_generators"]} >= {
        "big_move_intelligence", "money_intelligence",
    }


def test_single_deep_candidate_continues_without_disabling_generators():
    payload = example_queue()
    payload["candidates"][0].update(stage="DEEP_VALIDATION", work_mode="DEEP")
    payload["lifecycle_phase"] = "DEEP_VALIDATION"
    payload["active_deep_candidate"] = {"fingerprint_id": "TEST-BOUNDARY-v1"}
    before = copy.deepcopy(payload)
    result = snapshot(payload)
    assert result["next_action"] == {
        "action": "CONTINUE_SINGLE_DEEP_VALIDATION",
        "hypothesis_id": "TEST-BOUNDARY",
        "fingerprint_id": "TEST-BOUNDARY-v1",
    }
    assert result["trade_authority"] is False
    assert result["broker_connected"] is False
    assert len(result["independent_generators"]) == 2
    assert payload == before


def test_canonical_snapshot_preserves_state_without_assuming_screen_readiness():
    payload = load_queue()
    before = copy.deepcopy(payload)
    result = snapshot(payload)
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["broker_connected"] is False
    assert payload == before

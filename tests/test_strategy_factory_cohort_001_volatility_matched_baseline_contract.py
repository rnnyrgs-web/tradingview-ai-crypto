from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORTS = ROOT / "orchestration" / "cohorts"
CONTRACT_PATH = COHORTS / "strategy_factory_cohort_001_volatility_matched_baseline_contract.json"
PLAN_PATH = COHORTS / "strategy_factory_cohort_001_baseline_halving_plan.json"
BASELINE_PATH = COHORTS / "strategy_factory_cohort_001_baseline_execution_contract.json"
OCCUPANCY_PATH = COHORTS / "strategy_factory_cohort_001_randomized_placebo_source_occupancy_amendment.json"

EXPECTED_PLAN_SHA256 = "4cf46291af242a350d065bf24418b8fdf5c6d36e4fea1b923a9cb1a51046c392"
EXPECTED_BASELINE_SHA256 = "4525c3a192d56cf0f02284e3f6d910a00a1ce5870deffb95b05543165f175519"
EXPECTED_OCCUPANCY_SHA256 = "78518ae72cefc31db5944653fedb8e7c8a133911ebd5cdd7183f9fb096d66771"
EXPECTED_CONTRACT_SHA256 = "463039fd9e7956988a2ec579e9e3d7836086d6b9799198cdd8ae77cd13b83e2f"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_volatility_matched_contract_is_self_authenticated_and_parent_bound() -> None:
    contract = _load(CONTRACT_PATH)
    plan = _load(PLAN_PATH)
    baseline = _load(BASELINE_PATH)
    occupancy = _load(OCCUPANCY_PATH)

    unsigned_plan = dict(plan)
    assert unsigned_plan.pop("planning_contract_sha256") == EXPECTED_PLAN_SHA256
    assert _canonical_sha256(unsigned_plan) == EXPECTED_PLAN_SHA256

    unsigned_baseline = dict(baseline)
    assert unsigned_baseline.pop("baseline_execution_contract_sha256") == EXPECTED_BASELINE_SHA256
    assert _canonical_sha256(unsigned_baseline) == EXPECTED_BASELINE_SHA256

    unsigned_occupancy = dict(occupancy)
    assert unsigned_occupancy.pop("amendment_sha256") == EXPECTED_OCCUPANCY_SHA256
    assert _canonical_sha256(unsigned_occupancy) == EXPECTED_OCCUPANCY_SHA256

    bindings = contract["parent_bindings"]
    assert bindings["baseline_halving_plan"]["planning_contract_sha256"] == EXPECTED_PLAN_SHA256
    assert bindings["baseline_execution_contract"]["baseline_execution_contract_sha256"] == EXPECTED_BASELINE_SHA256
    assert bindings["source_occupancy_amendment"]["amendment_sha256"] == EXPECTED_OCCUPANCY_SHA256

    unsigned_contract = dict(contract)
    assert unsigned_contract.pop("contract_sha256") == EXPECTED_CONTRACT_SHA256
    assert _canonical_sha256(unsigned_contract) == EXPECTED_CONTRACT_SHA256


def test_control_scope_matches_only_the_five_power_eligible_stage1_candidates() -> None:
    contract = _load(CONTRACT_PATH)
    baseline = _load(BASELINE_PATH)

    expected = [row["fingerprint_id"] for row in baseline["candidate_controls"]]
    assert contract["candidate_scope"]["fingerprint_ids"] == expected
    assert contract["candidate_scope"]["candidate_count"] == 5

    withheld = contract["candidate_scope"]["withheld_candidate"]
    assert withheld["fingerprint_id"] == "DISC-WEEKEND-NORMALIZE-001-v1"
    assert withheld["status"] == "INCONCLUSIVE_POWER_PRE_OUTCOME"
    assert withheld["volatility_matched_control_authority"] is False

    defect = contract["defect"]
    assert defect["classification"] == "PRE_OUTCOME_BASELINE_GAUNTLET_COVERAGE_GAP"
    assert defect["outcomes_read"] is False
    assert defect["economic_negative_evidence"] is False


def test_pre_signal_volatility_state_is_exact_and_cannot_absorb_the_trigger_bar() -> None:
    contract = _load(CONTRACT_PATH)
    state = contract["volatility_state"]
    caliper = contract["matching_contract"]["caliper"]

    assert state["state_id"] == "PRE_SIGNAL-24H-HOURLY-REALIZED-VOL-v1"
    assert state["return_definition"] == "close[h] / close[h-1] - 1"
    assert state["window_returns"] == 24
    assert state["estimator"] == "sample_standard_deviation_ddof_1"
    assert "ending at t-1" in state["source_window"]
    assert "signal bar t is excluded" in state["source_window"]
    assert "ending at a-1" in state["control_window"]
    assert "control decision bar a is excluded" in state["control_window"]
    assert "finite strictly-positive sigma" in state["required_state"]
    assert "do not impute or widen" in state["required_state"]

    assert caliper["symmetric_sigma_ratio_max"] == 1.25
    assert math.isclose(caliper["absolute_log_sigma_ratio_max"], math.log(1.25), rel_tol=0.0, abs_tol=1e-15)
    assert caliper["per_constituent_required"] is True
    assert caliper["post_result_widening_allowed"] is False


def test_matching_is_one_shot_partition_safe_and_outcome_blind() -> None:
    contract = _load(CONTRACT_PATH)
    matching = contract["matching_contract"]
    scoring = contract["scoring_contract"]
    forbidden = contract["formation_forbidden_inputs"]

    assert matching["control_id"] == "VOLATILITY-MATCHED-TIMING-v1"
    assert "exactly one immutable volatility-matched control template" in matching["source_unit"]
    assert "same training partition or same frozen validation half" in matching["partition_rule"]
    assert matching["without_replacement"] is True
    assert "scarcity first" in matching["assignment_order"]
    assert "maximum constituent abs(log(sigma_control/sigma_source))" in matching["anchor_rank"]
    assert "One deterministic assignment only" in matching["no_redraw"]
    assert "widen the caliper" in matching["no_redraw"]
    assert "DATA/PIT_INCONCLUSIVE_VOLATILITY_MATCH_POOL" in matching["insufficient_pool"]
    assert "not treat pool insufficiency as negative economic evidence" in matching["insufficient_pool"]
    assert "maximum-possible-occupancy" in matching["source_occupancy_exclusion"]
    assert "may not free an anchor" in matching["control_occupancy"]
    assert "qualifying signal timestamp" in matching["candidate_signal_exclusion"]

    assert scoring["score_only_after_stage1_survival"] is True
    assert scoring["schedule_before_outcomes"] is True
    assert scoring["costs_bps"] == [24.0, 48.0, 72.0]
    assert "same fixed 1/3-NAV slot" in scoring["portfolio_slot"]
    assert "without recomputing the candidate signal" in scoring["fixed_hold_candidates"]
    assert "do not reapply the candidate entry gate" in scoring["range_auction_dynamic_exit"]
    assert "do not recompute whether the candidate residual/correlation signal qualifies" in scoring["residual_pair"]
    assert "exactly one template per source Stage-1 independent-event cluster" in scoring["independent_event_count"]

    assert "candidate or control entry-to-exit return" in forbidden
    assert "candidate or control P&L" in forbidden
    assert "candidate or control realized early-exit time" in forbidden
    assert "genuine-forward outcomes" in forbidden


def test_volatility_match_has_falsification_only_authority_and_keeps_evidence_closed() -> None:
    contract = _load(CONTRACT_PATH)
    locks = contract["authority_locks"]

    assert locks["stage1_outcomes_read_to_form_contract"] is False
    assert locks["baseline_outcomes_read_to_form_contract"] is False
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["post_outcome_matching_change_allowed"] is False
    assert locks["promotion_authority"] is False
    assert locks["broker_connected"] is False
    assert locks["trade_authority"] is False
    assert "Stage-2 falsification authority only" in contract["scoring_contract"]["incremental_value_use"]
    assert contract["status"] == "OUTCOME_BLIND_FROZEN_WAIT_STAGE1_SURVIVORS"
    assert "Do not implement or execute this control now merely to consume capacity" in contract["next_transition"]

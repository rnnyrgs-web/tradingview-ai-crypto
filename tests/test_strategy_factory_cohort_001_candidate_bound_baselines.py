from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORTS = ROOT / "orchestration" / "cohorts"
PLAN_PATH = COHORTS / "strategy_factory_cohort_001_baseline_halving_plan.json"
BINDING_PATH = COHORTS / "strategy_factory_cohort_001_stage1_binding.json"
EXECUTION_PATH = COHORTS / "strategy_factory_cohort_001_stage1_execution_contract.json"
BUNDLE_PATH = COHORTS / "strategy_factory_cohort_001_candidate_bound_baselines.json"

EXPECTED_ACTIVE = (
    "DISC-RESIDUAL-REV-001-v1",
    "DISC-SIGNED-VOLUME-DRIFT-001-v1",
    "DISC-LOWVOL-DRIFT-REV-001-v1",
    "DISC-MODERATEVOL-AUTOCORR-001-v1",
    "DISC-RANGE-AUCTION-REV-001-v1",
)
WITHHELD = "DISC-WEEKEND-NORMALIZE-001-v1"
SEED_SUFFIX = "randomized_timing_v1"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_candidate_bound_baseline_bundle_is_outcome_blind_and_self_authenticated() -> None:
    bundle = _load(BUNDLE_PATH)
    claimed = bundle["bundle_sha256"]
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256")
    assert _canonical_sha256(unsigned) == claimed

    assert bundle["status"] == "OUTCOME_BLIND_FROZEN_WAIT_STAGE1_SURVIVORS"
    assert bundle["formation_locks"] == {
        "stage1_or_baseline_outcomes_read": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "post_outcome_baseline_substitution_allowed": False,
        "post_outcome_threshold_tuning_allowed": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
    }


def test_bundle_binds_current_plan_admission_and_execution_identities() -> None:
    bundle = _load(BUNDLE_PATH)
    plan = _load(PLAN_PATH)
    binding = _load(BINDING_PATH)
    execution = _load(EXECUTION_PATH)

    plan_unsigned = dict(plan)
    plan_claimed = plan_unsigned.pop("planning_contract_sha256")
    assert _canonical_sha256(plan_unsigned) == plan_claimed

    assert bundle["source_baseline_halving_plan"] == {
        "cohort_planning_id": plan["cohort_planning_id"],
        "planning_contract_sha256": plan["planning_contract_sha256"],
    }
    assert bundle["source_stage1_binding"] == {
        "binding_id": binding["binding_id"],
        "binding_receipt_sha256": binding["binding_receipt_sha256"],
    }
    assert bundle["source_stage1_execution_contract"] == {
        "contract_id": execution["contract_id"],
        "execution_contract_sha256": execution["execution_contract_sha256"],
    }
    assert binding["baseline_halving_plan"] == bundle["source_baseline_halving_plan"]


def test_all_five_economically_executable_candidates_are_bound_before_outcomes() -> None:
    bundle = _load(BUNDLE_PATH)
    plan = _load(PLAN_PATH)
    binding = _load(BINDING_PATH)

    assert tuple(bundle["allocation"]["active_candidate_ids"]) == EXPECTED_ACTIVE
    assert bundle["allocation"]["economically_executable_candidate_count"] == len(EXPECTED_ACTIVE)
    assert bundle["allocation"]["withheld_candidate"]["fingerprint_id"] == WITHHELD
    assert bundle["allocation"]["withheld_candidate"]["status"] == "INCONCLUSIVE_POWER_PRE_OUTCOME"

    plan_by_id = {row["fingerprint_id"]: row for row in plan["candidate_baselines"]}
    binding_by_id = {row["fingerprint_id"]: row for row in binding["eligible_stage1_candidates"]}
    bundle_by_id = {row["fingerprint_id"]: row for row in bundle["candidate_bound_baselines"]}

    assert tuple(bundle_by_id) == EXPECTED_ACTIVE
    assert WITHHELD not in bundle_by_id

    for candidate_id in EXPECTED_ACTIVE:
        frozen = bundle_by_id[candidate_id]
        admitted = binding_by_id[candidate_id]
        planned = plan_by_id[candidate_id]

        assert frozen["status"] == "BOUND_PRE_OUTCOME_NOT_EXECUTED"
        assert frozen["scientific_design_sha256"] == admitted["scientific_design_sha256"]
        assert frozen["strategy_behavior_sha256"] == admitted["strategy_behavior_sha256"]
        assert frozen["contract_sha256"] == admitted["contract_sha256"]
        assert frozen["primary_mechanism_baseline"] == planned["primary_mechanism_baseline"]
        assert frozen["additional_falsifiers"] == planned["additional_falsifiers"]

        payload = {
            "candidate_scientific_design_sha256": admitted["scientific_design_sha256"],
            "planning_contract_sha256": plan["planning_contract_sha256"],
            "primary_mechanism_baseline": planned["primary_mechanism_baseline"],
            "additional_falsifiers": planned["additional_falsifiers"],
        }
        assert _canonical_sha256(payload) == frozen["candidate_baseline_bundle_sha256"]

        seed_material = (
            f"{plan['cohort_planning_id']}|{admitted['scientific_design_sha256']}|{SEED_SUFFIX}"
        )
        seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
        assert frozen["randomized_timing_seed"]["first_16_hex"] == seed_digest[:16]
        assert frozen["randomized_timing_seed"]["uint64"] == int(seed_digest[:16], 16)


def test_weekend_power_cut_does_not_become_economic_rejection_or_baseline_execution() -> None:
    bundle = _load(BUNDLE_PATH)
    withheld = bundle["allocation"]["withheld_candidate"]
    assert withheld["fingerprint_id"] == WITHHELD
    assert withheld["status"] == "INCONCLUSIVE_POWER_PRE_OUTCOME"
    assert "do not open Cohort-001 economic outcomes" in withheld["reason"]
    assert all(row["fingerprint_id"] != WITHHELD for row in bundle["candidate_bound_baselines"])


def test_execution_rule_forbids_post_result_control_substitution_or_seed_redraw() -> None:
    bundle = _load(BUNDLE_PATH)
    rule = bundle["execution_rule"]
    assert "pre-bound" in rule or "already-bound" in rule
    assert "No post-result baseline substitution" in rule
    assert "seed redraw" in rule
    assert "protected-OOS/forward" in rule

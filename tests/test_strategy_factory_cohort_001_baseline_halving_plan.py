import hashlib
import json
from pathlib import Path


PLAN_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_baseline_halving_plan.json")
EXPECTED_CANDIDATES = {
    "DISC-BREADTH-PERSIST-001-v1",
    "DISC-RESIDUAL-REV-001-v1",
    "DISC-SIGNED-VOLUME-DRIFT-001-v1",
    "DISC-LOWVOL-DRIFT-REV-001-v1",
    "DISC-WEEKEND-NORMALIZE-001-v1",
    "DISC-MODERATEVOL-AUTOCORR-001-v1",
    "DISC-RANGE-AUCTION-REV-001-v1",
    "DISC-DELTA-CARRY-001-v1",
}


def _load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _self_digest(plan: dict) -> str:
    payload = dict(plan)
    payload.pop("planning_contract_sha256", None)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_planning_contract_digest_is_reproducible() -> None:
    plan = _load_plan()
    assert plan["planning_contract_sha256"] == _self_digest(plan)


def test_candidate_set_and_fail_closed_holds_are_frozen() -> None:
    plan = _load_plan()
    candidates = {row["fingerprint_id"]: row for row in plan["candidate_baselines"]}
    assert set(candidates) == EXPECTED_CANDIDATES
    assert candidates["DISC-BREADTH-PERSIST-001-v1"]["status"] == "HELD_ACTIVE_OWNERSHIP_COLLISION"
    assert candidates["DISC-DELTA-CARRY-001-v1"]["status"] == "WAIT_520_DATA_READY"


def test_evidence_and_authority_locks_remain_closed() -> None:
    locks = _load_plan()["global_evidence_locks"]
    assert locks["selection_data_only"] is True
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["broker_connected"] is False
    assert locks["trade_authority"] is False
    assert locks["post_outcome_baseline_substitution_allowed"] is False
    assert locks["post_outcome_threshold_tuning_allowed"] is False


def test_successive_halving_keeps_one_deep_candidate_and_baseline_incrementality() -> None:
    plan = _load_plan()
    gate = plan["stage_2_incremental_value_gate"]
    requirements = " ".join(gate["hard_requirements"]).lower()
    assert "baseline" in requirements
    assert "training" in requirements
    assert "validation" in requirements
    assert plan["medium_stage_ranking"]["max_expensive_deep_candidates"] == 1
    assert plan["medium_stage_ranking"]["protected_oos_or_forward_inputs_forbidden"] is True


def test_randomized_placebo_is_outcome_blind_and_deterministic() -> None:
    randomized = _load_plan()["baseline_generation_rules"]["randomized_timing"]
    assert randomized["no_outcome_conditioning"] is True
    assert "SHA256" in randomized["seed_rule"]
    assert "without replacement" in randomized["matching"]
    assert "training and validation" in randomized["matching"]

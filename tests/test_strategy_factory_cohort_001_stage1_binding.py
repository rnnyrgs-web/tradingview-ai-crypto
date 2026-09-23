import hashlib
import json
from pathlib import Path


BINDING_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_stage1_binding.json")
ADMISSION_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json")
PLAN_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_baseline_halving_plan.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _self_digest(binding: dict) -> str:
    payload = dict(binding)
    payload.pop("binding_receipt_sha256", None)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_binding_receipt_digest_is_reproducible() -> None:
    binding = _load(BINDING_PATH)
    assert binding["binding_receipt_sha256"] == _self_digest(binding)


def test_stage1_binding_matches_canonical_admission_exactly() -> None:
    binding = _load(BINDING_PATH)
    admission = _load(ADMISSION_PATH)
    admitted = {row["fingerprint_id"]: row for row in admission["candidates"]}
    eligible = {row["fingerprint_id"]: row for row in binding["eligible_stage1_candidates"]}
    excluded = {row["fingerprint_id"]: row for row in binding["excluded_stage1_candidates"]}

    expected_eligible = {
        row["fingerprint_id"]
        for row in admission["candidates"]
        if row["screening_authority"] is True
    }
    expected_excluded = {
        row["fingerprint_id"]
        for row in admission["candidates"]
        if row["screening_authority"] is False
    }
    assert set(eligible) == expected_eligible
    assert set(excluded) == expected_excluded

    for fingerprint_id, bound in eligible.items():
        canonical = admitted[fingerprint_id]
        assert bound["scientific_design_sha256"] == canonical["scientific_design_sha256"]
        assert bound["strategy_behavior_sha256"] == canonical["strategy_behavior_sha256"]
        assert bound["contract_sha256"] == canonical["contract_sha256"]
        assert bound["admission_status"] == canonical["status"]
        assert canonical["selection_dataset_receipt_sha256"] == admission["selection_dataset_qualification"]["receipt_sha256"]
        assert canonical["trade_authority"] is False
        assert canonical["untouched_oos_opened"] is False
        assert canonical["genuine_forward_opened"] is False

    for fingerprint_id, bound in excluded.items():
        canonical = admitted[fingerprint_id]
        assert bound["admission_status"] == canonical["status"]
        assert canonical["screening_authority"] is False


def test_binding_uses_frozen_baseline_plan_and_admission_receipts() -> None:
    binding = _load(BINDING_PATH)
    admission = _load(ADMISSION_PATH)
    plan = _load(PLAN_PATH)

    assert binding["baseline_halving_plan"]["planning_contract_sha256"] == plan["planning_contract_sha256"]
    assert binding["canonical_admission"]["receipt_sha256"] == admission["receipt_sha256"]
    assert binding["canonical_admission"]["selection_dataset_receipt_sha256"] == admission["selection_dataset_qualification"]["receipt_sha256"]
    assert binding["canonical_admission"]["outcomes_read"] is False
    assert admission["outcomes_read"] is False

    plan_gate = plan["cheap_stage"]["candidate_economic_gate"]
    for key, value in binding["cheap_stage_gate"].items():
        assert plan_gate[key] == value


def test_stage1_cost_stress_is_bound_to_canonical_admission() -> None:
    binding = _load(BINDING_PATH)
    admission = _load(ADMISSION_PATH)
    bound_cost = binding["stage1_cost_contract"]
    canonical_cost = admission["stage1_cost_contract"]

    for key in (
        "fees_bps",
        "spread_bps",
        "slippage_bps",
        "adverse_funding_allowance_bps_per_trade",
        "stress_totals_bps",
        "deeper_validation_requires_pit_funding",
    ):
        assert bound_cost[key] == canonical_cost[key]
    assert bound_cost["stress_totals_bps"] == {"1x": 24.0, "2x": 48.0, "3x": 72.0}


def test_protected_and_trading_authority_remain_closed() -> None:
    binding = _load(BINDING_PATH)
    locks = binding["evidence_locks"]
    authority = binding["execution_authority"]

    assert locks["selection_data_only"] is True
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["broker_connected"] is False
    assert locks["trade_authority"] is False
    assert locks["outcomes_read_to_form_binding"] is False
    assert locks["post_outcome_threshold_tuning_allowed"] is False

    assert authority["may_prepare_deterministic_stage1_code"] is True
    assert authority["may_execute_stage1_before_parent_515_integrates_and_exact_head_review_clears"] is False
    assert authority["may_read_protected_oos"] is False
    assert authority["may_promote_strategy"] is False
    assert authority["may_trade"] is False

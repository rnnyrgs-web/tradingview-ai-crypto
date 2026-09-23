from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_multiplicity_authority.json"
)
SEED_PATH = ROOT / "orchestration" / "cohorts" / "strategy_factory_cohort_001_seed.json"
RECEIPT_PATH = (
    ROOT
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_canonical_admission.json"
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _contract_digest(payload: dict) -> str:
    unhashed = dict(payload)
    unhashed.pop("contract_sha256")
    canonical = json.dumps(
        unhashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_multiplicity_contract_is_self_bound_and_matches_original_family() -> None:
    contract = _load(CONTRACT_PATH)
    seed = _load(SEED_PATH)
    receipt = _load(RECEIPT_PATH)

    assert contract["contract_sha256"] == _contract_digest(contract)
    assert contract["status"] == "OUTCOME_BLIND_FROZEN"

    family = contract["family"]
    seed_family = seed["multiple_testing"]
    seed_members = [row["fingerprint_id"] for row in seed["candidates"]]

    assert family["family_id"] == seed_family["family_id"]
    assert family["planned_hypothesis_count"] == seed_family["planned_hypothesis_count"] == 8
    assert family["members"] == seed_members
    assert len(set(family["members"])) == 8
    assert family["failed_blocked_or_underpowered_members_remain_counted"] is True
    assert family["family_membership_is_fixed_before_outcomes"] is True
    assert family["renaming_or_cosmetic_variants_cannot_reset_family"] is True

    assert receipt["multiple_testing_family_id"] == family["family_id"]
    assert receipt["planned_hypothesis_count"] == 8


def test_confirmatory_alpha_is_fixed_before_outcomes_and_never_recycled() -> None:
    contract = _load(CONTRACT_PATH)
    budget = contract["confirmatory_familywise_error_budget"]

    family_alpha = Decimal(budget["familywise_alpha"])
    per_hypothesis = Decimal(budget["per_hypothesis_alpha"])
    assert family_alpha == Decimal("0.05")
    assert per_hypothesis == family_alpha / Decimal(8) == Decimal("0.00625")
    assert budget["allocation_method"] == "BONFERRONI_FIXED_EQUAL_ACROSS_ALL_8_ORIGINAL_HYPOTHESES"
    assert budget["alpha_recycling_after_failure_block_or_underpower"] is False
    assert budget["alpha_reallocation_after_results"] is False
    assert budget["optional_stopping_or_repeated_peeking_allowed"] is False
    assert budget["protected_oos_may_be_opened_to_choose_test_method"] is False
    assert budget["confirmatory_test_method_must_be_frozen_before_any_protected_oos_or_genuine_forward_read"] is True
    assert budget["no_inferential_claim_until_exact_confirmatory_method_is_frozen"] is True


def test_stage1_remains_noninferential_and_cost_proxy_cannot_promote() -> None:
    contract = _load(CONTRACT_PATH)
    receipt = _load(RECEIPT_PATH)
    stage1 = contract["stage1_multiplicity_semantics"]
    costs = contract["cost_authority"]

    assert stage1["stage1_is_inferential_significance_test"] is False
    assert stage1["stage1_is_economic_falsification_screen"] is True
    assert stage1["stage1_pass_grants_statistical_significance"] is False
    assert stage1["stage1_pass_grants_profitability_authentication"] is False
    assert stage1["stage1_pass_grants_oos_or_forward_authority"] is False
    assert stage1["stage1_pass_grants_promotion_or_trading_authority"] is False
    assert stage1["single_expensive_deep_candidate_max"] == 1

    frozen_totals = receipt["stage1_cost_contract"]["stress_totals_bps"]
    assert costs["stage1_cost_totals_bps"] == [
        str(int(frozen_totals["1x"])),
        str(int(frozen_totals["2x"])),
        str(int(frozen_totals["3x"])),
    ]
    assert costs["stage1_costs_are_screening_falsifiers_not_empirical_execution_cost_proof"] is True
    assert costs["generic_spread_slippage_and_adverse_funding_allowance_are_not_venue_notional_time_specific_evidence"] is True
    assert costs["non_carry_ohlcv_candidate_survival_requires_pit_venue_execution_cost_and_funding_evidence_before_deep_validation_or_profitability_claim"] is True
    assert costs["delta_carry_candidate_is_not_covered_by_the_non_carry_stage1_cost_proxy"] is True
    assert costs["delta_carry_screening_remains_data_blocked_until_its_separate_trusted_spot_perpetual_funding_contract_clears"] is True
    assert costs["a_72bps_stage1_pass_cannot_substitute_for_later_authenticated_cost_evidence"] is True

    locks = contract["evidence_locks"]
    assert locks == {
        "broker_connected": False,
        "genuine_forward_opened": False,
        "post_outcome_alpha_or_cost_semantics_changes_allowed": False,
        "protected_oos_opened": False,
        "strategy_outcomes_read_to_form_contract": False,
        "trade_authority": False,
    }

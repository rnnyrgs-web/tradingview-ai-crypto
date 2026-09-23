from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORTS = ROOT / "orchestration" / "cohorts"
AMENDMENT_PATH = COHORTS / "strategy_factory_cohort_001_randomized_placebo_source_occupancy_amendment.json"
PARENT_PATH = COHORTS / "strategy_factory_cohort_001_baseline_execution_contract.json"

EXPECTED_PARENT_SHA256 = "4525c3a192d56cf0f02284e3f6d910a00a1ce5870deffb95b05543165f175519"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_source_occupancy_amendment_is_self_authenticated_and_parent_bound() -> None:
    parent = _load(PARENT_PATH)
    amendment = _load(AMENDMENT_PATH)

    unsigned_parent = dict(parent)
    parent_claimed = unsigned_parent.pop("baseline_execution_contract_sha256")
    assert parent_claimed == EXPECTED_PARENT_SHA256
    assert _canonical_sha256(unsigned_parent) == EXPECTED_PARENT_SHA256

    binding = amendment["parent_baseline_execution_contract"]
    assert binding["contract_id"] == parent["contract_id"]
    assert binding["baseline_execution_contract_sha256"] == EXPECTED_PARENT_SHA256
    assert binding["path"] == str(PARENT_PATH.relative_to(ROOT))

    unsigned_amendment = dict(amendment)
    claimed = unsigned_amendment.pop("amendment_sha256")
    assert _canonical_sha256(unsigned_amendment) == claimed


def test_source_exclusion_and_placebo_occupancy_use_same_maximum_interval_convention() -> None:
    parent = _load(PARENT_PATH)
    amendment = _load(AMENDMENT_PATH)
    randomized = parent["common_controls"]["randomized_timing"]
    rules = amendment["normative_rules"]

    # The parent already made placebo-side occupancy outcome blind.
    assert "maximum possible exposure interval" in randomized["outcome_blind_occupancy"]
    assert "realized outcome-dependent early exit" in randomized["outcome_blind_occupancy"]

    # The amendment closes only the source-side exclusion ambiguity.
    assert rules["source_candidate_exclusion_basis"] == "MAXIMUM_POSSIBLE_OCCUPANCY_ONLY"
    assert "does not change candidate Stage-1 scoring" in rules["source_cluster_identity"]
    assert "Only for excluding original candidate signal/exposure intervals" in rules[
        "source_exclusion_interval_formation"
    ]
    assert "Do not shorten that exclusion" in rules["source_exclusion_interval_formation"]
    assert "reserved maximum-exposure interval" in rules["anchor_overlap_rule"]
    assert "source candidate reserved maximum-exposure interval" in rules["anchor_overlap_rule"]
    assert "union of all constituent maximum-occupancy intervals" in rules["cluster_concurrency"]


def test_dynamic_range_auction_source_cannot_shorten_exclusion_from_realized_exit() -> None:
    parent = _load(PARENT_PATH)
    amendment = _load(AMENDMENT_PATH)
    candidate_ids = {row["fingerprint_id"] for row in parent["candidate_controls"]}
    randomized = parent["common_controls"]["randomized_timing"]
    rule = amendment["normative_rules"]["range_auction_candidate"]

    assert "DISC-RANGE-AUCTION-REV-001-v1" in candidate_ids
    assert "range-auction reversion preserve the 6h maximum occupancy" in randomized["template_fields"]
    assert "t+1 entry open through the t+7 open" in rule
    assert "regardless of whether the realized path would trigger" in rule


def test_pool_insufficiency_stays_fail_closed_without_redraw_or_realized_exit_fallback() -> None:
    amendment = _load(AMENDMENT_PATH)
    rules = amendment["normative_rules"]
    locks = amendment["authority_locks"]

    assert "DATA/PIT_INCONCLUSIVE_RANDOMIZED_PLACEBO_POOL" in rules["insufficient_pool"]
    assert "Do not fall back to realized-exit exclusions" in rules["insufficient_pool"]
    assert locks["stage1_outcomes_opened_to_form_amendment"] is False
    assert locks["baseline_outcomes_opened_to_form_amendment"] is False
    assert locks["post_outcome_redraw_allowed"] is False
    assert locks["post_outcome_pool_redefinition_allowed"] is False
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["promotion_authority"] is False
    assert locks["broker_connected"] is False
    assert locks["trade_authority"] is False
    assert amendment["status"] == "OUTCOME_BLIND_FROZEN_NORMATIVE_NARROWING"

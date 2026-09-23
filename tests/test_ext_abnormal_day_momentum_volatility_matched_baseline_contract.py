from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_abnormal_day_momentum_001_volatility_matched_baseline.json"
)
EXPECTED_CONTRACT_ID = (
    "EXT-ABNORMAL-DAY-MOMENTUM-001-v1-VOLATILITY-MATCHED-BASELINE-v1"
)
EXPECTED_DIGEST = "bff0247f066bcda200569c9aea788e6ad1defbaf520dec7f97ed7ee0833e12d2"
EXPECTED_STAGE1_HEAD = "31150ede8bc52e051380c04fcab3b496f4750de4"


def _load() -> dict[str, object]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _canonical_digest(contract: dict[str, object]) -> str:
    payload = dict(contract)
    payload.pop("contract_sha256", None)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    # Git object identity is SHA-1 by definition here; this is not a security hash.
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def test_contract_is_self_digested_and_pinned_before_outcomes() -> None:
    contract = _load()
    assert contract["contract_id"] == EXPECTED_CONTRACT_ID
    assert contract["formed_before_replication_outcomes"] is True
    assert contract["source_stage1_head_sha"] == EXPECTED_STAGE1_HEAD
    assert contract["regenerate_if_source_stage1_head_changes"] is True
    assert contract["contract_sha256"] == EXPECTED_DIGEST
    assert _canonical_digest(contract) == EXPECTED_DIGEST


def test_all_source_bytes_are_bound_to_the_frozen_stage1_identity() -> None:
    contract = _load()
    bindings = contract["source_bindings"]
    assert isinstance(bindings, list)
    expected_paths = {
        "orchestration/external_replication/ext_abnormal_day_momentum_001_v1.json",
        "orchestration/external_replication/ext_abnormal_day_momentum_001_stage1_execution.json",
        "orchestration/external_replication/abnormal_day_momentum_runner.py",
        "orchestration/cohorts/strategy_factory_cohort_001_baseline_halving_plan.json",
    }
    assert {binding["path"] for binding in bindings} == expected_paths
    for binding in bindings:
        path = ROOT / binding["path"]
        assert path.is_file()
        assert _git_blob_sha1(path) == binding["git_blob_sha1"]


def test_matching_rule_is_outcome_blind_and_cannot_be_relaxed_post_result() -> None:
    contract = _load()
    formation = contract["formation"]
    volatility = formation["volatility_state"]

    assert formation["authoritative_source_unit"] == "unique_utc_signal_day_portfolio_block"
    assert formation["source_candidate_days_excluded"] is True
    assert formation["control_days_without_replacement"] is True
    assert formation["sample_shrinking_allowed"] is False
    assert formation["post_outcome_redraw_or_rematch_allowed"] is False

    assert volatility["must_match_candidate_reference_std_definition"] is True
    assert volatility["current_day_excluded"] is True
    assert volatility["finite_and_gt_zero_required"] is True
    assert volatility["per_leg_symmetric_sigma_ratio_max"] == 1.25
    assert math.isclose(
        volatility["equivalent_log_distance_max"],
        math.log(1.25),
        rel_tol=0.0,
        abs_tol=1e-15,
    )
    assert volatility["caliper_widening_after_results_allowed"] is False
    assert volatility["alternative_calipers_or_buckets_allowed"] is False

    forbidden = set(formation["selection_features_forbidden"])
    assert {
        "control-day forward return",
        "control-day entry-to-exit P&L",
        "candidate forward return or P&L",
        "protected OOS values",
        "genuine-forward outcomes",
    } <= forbidden


def test_stage2_scoring_reuses_candidate_cost_sizing_and_authority_locks() -> None:
    contract = _load()
    scoring = contract["scoring"]
    stage2 = contract["stage2_use"]
    authority = contract["authority"]

    assert scoring["same_candidate_cost_semantics"] is True
    assert scoring["base_total_cost_bps"] == 24.0
    assert scoring["middle_total_cost_bps"] == 48.0
    assert scoring["stress_total_cost_bps"] == 72.0
    assert scoring["same_portfolio_sizing_and_utc_day_aggregation"] is True
    assert scoring["nav_fraction_per_eligible_instrument"] == 1 / 3
    assert scoring["max_gross_nav_fraction"] == 1.0
    assert scoring["final_same_day_signal_count_normalization_allowed"] is False
    assert scoring["raw_asset_event_statistics_authoritative"] is False
    assert scoring["protected_oos_may_be_read"] is False

    assert stage2["run_only_if_stage1_survives"] is True
    assert stage2["run_once_without_post_outcome_rematching"] is True
    assert stage2["candidate_must_add_incremental_economic_value"] is True
    assert stage2["failed_or_inconclusive_result_routes_to_issue_510"] is True
    assert stage2["control_result_may_not_redefine_candidate"] is True

    assert authority == {
        "research_only": True,
        "stage1_execution_authority": False,
        "stage2_execution_authority_before_stage1_survival": False,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
    }

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "orchestration/external_replication/ext_eth_session_reversal_001_v1.json"
)


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _self_digest(contract: dict) -> str:
    payload = dict(contract)
    payload.pop("artifact_sha256")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_predeclaration_self_digest_is_immutable() -> None:
    contract = _contract()
    assert contract["artifact_sha256"] == _self_digest(contract)
    assert contract["artifact_sha256"] == (
        "fee604ea0e2f993cd109cadcc6717deedbb7bd02e044cf380de2ef80e91afcc3"
    )


def test_external_source_identity_strategy_and_publication_date_are_frozen() -> None:
    contract = _contract()
    source = contract["source_research"]
    semantics = source["external_code_semantics"]

    assert source["replication_repository"] == "wzf01195010-png/Crypto-day-night-effects"
    assert source["replication_repository_commit"] == (
        "5693993e108f2b3668bd21b1dd36ae31f79d8fcd"
    )
    assert source["replication_code_blob_sha"] == (
        "82b79f2be4332858de55de46341bd3fc81fa0c38"
    )
    assert source["publication_date"] == "2026-09-06"
    assert source["published_results_are_internal_evidence"] is False
    assert "retrospective post-source-sample" in source["source_selection_warning"]
    assert "not a prospective/live" in source["source_selection_warning"]
    assert semantics == {
        "timezone": "UTC",
        "eth_cutoff_hour_utc": 5,
        "day_window": "05:00-17:00 UTC",
        "night_window": "17:00-05:00 UTC",
        "night_rule": "LONG",
        "day_rule": "REVERSAL_OF_PREVIOUS_SAME_SESSION_RETURN",
        "source_data_sample_end": "2025-12-31T23:00:00Z",
    }


def test_replication_uses_only_2026_incrementals_and_future_evidence_is_sealed() -> None:
    contract = _contract()
    data = contract["data_contract"]

    assert data["required_incremental_archives"] == [
        "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q1.zip",
        "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q2.zip",
    ]
    assert data["required_data_start_utc"] == "2026-01-01T04:00:00Z"
    assert "close.pct_change()" in data["incremental_archive_reason"]
    assert "context-only" in data["warmup_context_authority"]
    assert data["scored_trading_date_start"] == "2026-01-02"
    assert data["scored_trading_date_end"] == "2026-06-30"
    assert data["validation_half_1_trading_dates"] == (
        "2026-01-02 through 2026-03-31 inclusive"
    )
    assert data["validation_half_2_trading_dates"] == (
        "2026-04-01 through 2026-06-30 inclusive"
    )

    # July 1 through formation is historical at predeclaration time and cannot be
    # relabeled as prospective/genuine-forward evidence.
    assert "protected_shadow_start_utc" not in data
    assert data["retrospective_holdout_start_utc"] == "2026-07-01T00:00:00Z"
    assert data["retrospective_holdout_classification"] == (
        "SEALED_HISTORICAL_TAIL_NOT_GENUINE_FORWARD"
    )
    assert data["screen_may_read_retrospective_holdout"] is False

    # The independent sample unit is a full UTC trading date whose night leg starts
    # at 17:00 UTC. Formation occurred mid-night-session, so the first fully
    # post-formation trading date starts at the next 17:00 boundary.
    formed = _utc(contract["formed_at"])
    genuine_start = _utc(data["genuine_forward_shadow_start_utc"])
    assert data["predeclaration_time_utc"] == contract["formed_at"]
    assert genuine_start > formed
    assert data["genuine_forward_shadow_start_utc"] == "2026-09-24T17:00:00Z"
    assert data["genuine_forward_first_complete_trading_date"] == "2026-09-25"
    assert data["screen_may_read_genuine_forward_shadow"] is False
    assert data["no_paid_data_required"] is True


def test_retrospective_stage_one_cannot_claim_genuine_forward_authority() -> None:
    contract = _contract()
    stage = contract["successive_halving"]
    authority = contract["screening_authority"]

    assert "retrospective post-source-sample" in stage["stage_1"]
    assert "genuine-forward evidence begins only" in stage["stage_3"]
    assert stage["retrospective_holdout_opened"] is False
    assert stage["genuine_forward_shadow_opened"] is False
    assert authority["retrospective_holdout_opened"] is False
    assert authority["genuine_forward_shadow_opened"] is False
    assert authority["retrospective_h1_may_claim_genuine_forward"] is False
    assert "cannot be called genuine-forward evidence" in contract["scientific_hypothesis"][
        "falsifiable_claim"
    ]


def test_signal_has_one_fixed_cutoff_and_no_post_outcome_search() -> None:
    contract = _contract()
    signal = contract["signal_rules"]

    assert signal["parameter_variants"] == 1
    assert signal["cutoff_hour_utc"] == 5
    assert signal["night_position"] == 1
    assert signal["day_position"] == (
        "negative sign of the immediately previous completed 05:00-17:00 UTC "
        "daytime-session return"
    )
    assert "2026-01-01" in signal["first_replication_day_day_position"]
    assert "warmup only" in signal["first_replication_day_day_position"]
    assert signal["post_outcome_cutoff_search_allowed"] is False
    assert signal["post_outcome_rule_search_allowed"] is False
    assert signal["future_return_access_during_schedule_formation"] is False


def test_cost_ladder_is_screen_only_and_turnover_aware() -> None:
    contract = _contract()
    costs = contract["cost_model"]

    assert costs["stage_1_screen_only"] is True
    assert costs["base_total_bps_per_unit_turnover"] == 24.0
    assert costs["stress_total_bps_per_unit_turnover"] == [24.0, 48.0, 72.0]
    assert "long-to-short or short-to-long flip has turnover 2" in costs[
        "turnover_definition"
    ]
    assert costs["authenticated_execution_cost_claim_allowed"] is False
    assert "margin/borrow/funding" in costs["survivor_requirement"]


def test_stage_one_is_non_inferential_and_future_variants_stay_in_family() -> None:
    contract = _contract()
    multiplicity = contract["multiple_testing"]

    assert multiplicity["planned_primary_hypotheses"] == 1
    assert multiplicity["planned_parameter_variants"] == 1
    assert multiplicity["stage_1_is_non_inferential"] is True
    assert multiplicity["familywise_significance_claim_allowed_from_stage_1"] is False
    assert "different UTC cutoffs" in multiplicity["future_siblings_same_family"]
    assert "different day/night strategy pairs" in multiplicity[
        "future_siblings_same_family"
    ]


def test_baselines_falsify_incremental_reversal_value() -> None:
    contract = _contract()
    controls = contract["baseline_and_ablation_plan"]

    assert controls["formation_before_outcomes"] is True
    assert "night-only" in controls["complexity_rule"]
    assert "daytime MOMENTUM" in controls["sign_flip_falsifier"]
    assert "two trading dates earlier" in controls["one_session_delay"]
    stage_two_controls = controls["randomized_timing_and_volatility_match"]
    assert "Stage-1 survivor" in stage_two_controls
    assert "randomized-timing" in contract["successive_halving"]["stage_2"]
    assert "volatility-matched" in contract["successive_halving"]["stage_2"]
    assert "frozen" in stage_two_controls
    assert "independently reviewed" in stage_two_controls


def test_authority_remains_fail_closed_before_data_and_review() -> None:
    contract = _contract()
    authority = contract["screening_authority"]
    execution = contract["execution_rules"]

    assert authority["screen_started"] is False
    assert authority["requires_exact_data_preflight"] is True
    assert authority["requires_canonical_semantic_rejected_memory_check"] is True
    assert authority["requires_exact_head_ci"] is True
    assert authority["requires_independent_review"] is True
    assert authority["retrospective_holdout_opened"] is False
    assert authority["genuine_forward_shadow_opened"] is False
    assert authority["trade_authority"] is False
    assert authority["promotion_authority"] is False
    assert execution["broker_connected"] is False
    assert execution["live_trading"] is False

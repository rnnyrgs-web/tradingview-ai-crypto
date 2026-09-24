from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = (
    ROOT
    / "orchestration/external_replication/ext_eth_session_reversal_001_survivor_controls_v1.json"
)
PARENT_PATH = (
    ROOT
    / "orchestration/external_replication/ext_eth_session_reversal_001_v1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _self_digest(payload: dict) -> str:
    canonical = dict(payload)
    canonical.pop("artifact_sha256")
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _lag(seed: str, trading_date: str) -> int:
    digest = hashlib.sha256(f"{seed}|{trading_date}".encode("utf-8")).digest()
    return 3 + (int.from_bytes(digest[:8], "big") % 5)


def test_survivor_control_contract_self_digest_and_parent_binding() -> None:
    control = _load(CONTROL_PATH)
    parent = _load(PARENT_PATH)

    assert control["artifact_sha256"] == _self_digest(control)
    assert control["artifact_sha256"] == (
        "83ad1728763fb9a1d37f52d4084c7d7ebac931c873cd379a628b77c8ee47d1af"
    )
    parent_binding = control["parent_replication"]
    assert parent["replication_id"] == parent_binding["replication_id"]
    assert parent["artifact_sha256"] == parent_binding["predeclaration_artifact_sha256"]
    assert parent_binding["exact_head_sha"] == (
        "f3ae2ee6fd9ff648632ec3a557608af100902b08"
    )
    assert parent_binding["predeclaration_git_blob_sha"] == (
        "e27a19904130ceb0dcaff670b0eecb93b550103e"
    )
    assert parent_binding["parent_may_be_mutated_by_this_contract"] is False


def test_randomized_timing_placebo_is_causal_single_draw_and_outcome_blind() -> None:
    control = _load(CONTROL_PATH)
    placebo = control["randomized_timing_placebo"]

    assert placebo["lag_set"] == [3, 4, 5, 6, 7]
    assert placebo["common_support_start_date"] == "2026-01-08"
    assert placebo["common_support_end_date"] == "2026-06-30"
    assert placebo["single_draw"] is True
    assert placebo["redraw_allowed"] is False
    assert placebo["post_outcome_lag_search_allowed"] is False
    assert placebo["future_or_target_session_return_allowed_in_schedule_formation"] is False
    assert placebo["execution_boundaries"] == ["05:00 UTC", "17:00 UTC"]
    assert placebo["cost_ladder_bps_per_unit_turnover"] == [24.0, 48.0, 72.0]
    assert "Missing any required source or target session" in placebo[
        "lag_calendar_semantics"
    ]

    seed = placebo["seed_sha256"]
    assert seed == "1b84c1e4021cedaccf1e0364378c6b2cc8507d395d189bf07cf614e60b09a976"
    assert _lag(seed, "2026-01-08") == 4
    assert _lag(seed, "2026-01-09") == 5
    assert _lag(seed, "2026-03-31") == 7
    assert _lag(seed, "2026-04-01") == 5
    assert _lag(seed, "2026-06-30") == 3


def test_randomized_lags_use_only_prior_calendar_dates_and_fixed_common_support() -> None:
    control = _load(CONTROL_PATH)
    placebo = control["randomized_timing_placebo"]
    seed = placebo["seed_sha256"]

    current = date.fromisoformat(placebo["common_support_start_date"])
    end = date.fromisoformat(placebo["common_support_end_date"])
    seen = set()
    count = 0
    while current <= end:
        lag = _lag(seed, current.isoformat())
        seen.add(lag)
        source = current - timedelta(days=lag)
        assert 3 <= lag <= 7
        assert source < current
        assert source >= date(2026, 1, 1)
        count += 1
        current += timedelta(days=1)

    assert count == 174
    assert seen == {3, 4, 5, 6, 7}


def test_volatility_control_is_exact_cotemporal_not_posthoc_matching() -> None:
    control = _load(CONTROL_PATH)
    vol = control["volatility_matched_control"]

    assert vol["matching_method"] == "EXACT_SAME_DATE_SAME_SESSION_SAME_ABSOLUTE_EXPOSURE"
    assert vol["candidate_day_position"] == "-sign(previous completed daytime return)"
    assert vol["control_day_position"] == "+sign(previous completed daytime return)"
    assert vol["night_position_both"] == 1
    assert vol["same_dates"] is True
    assert vol["same_day_night_boundaries"] is True
    assert vol["same_absolute_day_exposure"] is True
    assert vol["same_realized_volatility_state"] is True
    assert vol["resampling"] is False
    assert vol["volatility_estimator_or_caliper"] is None
    assert vol["post_outcome_matching_choice_allowed"] is False
    assert "24 bps and 72 bps" in vol["comparison_rule"]
    assert "both frozen chronological halves" in vol["comparison_rule"]


def test_market_beta_is_a_strict_incremental_stage2_gate() -> None:
    control = _load(CONTROL_PATH)
    beta = control["market_beta_control"]

    assert beta["control_position_sequence"] == "LONG in both night and daytime sessions"
    assert beta["same_asset"] == "Kraken ETH/USD spot"
    assert beta["same_scored_dates"] is True
    assert beta["same_day_night_boundaries"] is True
    assert beta["candidate_max_gross_exposure"] == 1.0
    assert beta["control_max_gross_exposure"] == 1.0
    assert beta["cost_ladder_bps_per_unit_turnover"] == [24.0, 48.0, 72.0]
    assert beta["post_outcome_respecification_allowed"] is False
    assert "candidate cumulative arithmetic net PnL must exceed always-long" in beta[
        "comparison_rule"
    ]
    assert "both frozen chronological halves" in beta["comparison_rule"]


def test_full_517_baseline_gauntlet_is_classified_before_outcomes() -> None:
    control = _load(CONTROL_PATH)
    coverage = control["baseline_gauntlet_coverage"]

    assert set(coverage) == {
        "market_beta",
        "simple_trend",
        "simple_reversal",
        "randomized_timing",
        "one_period_delay",
        "volatility_matched",
        "ablation",
    }
    assert coverage["market_beta"]["status"] == (
        "FROZEN_PARENT_CONTROL_AND_STRICT_INCREMENTAL_GATE"
    )
    assert coverage["market_beta"]["strict_incremental_gate"] is True
    assert coverage["simple_trend"]["strict_incremental_gate"] is True
    assert coverage["randomized_timing"]["status"] == "FROZEN_BY_THIS_CONTRACT"
    assert coverage["one_period_delay"]["status"] == "FROZEN_PARENT_CONTROL"
    assert coverage["volatility_matched"]["status"] == "FROZEN_EXACT_SAME_DATE_MATCH"
    assert coverage["ablation"]["status"] == "FROZEN_PARENT_CONTROL"
    assert coverage["simple_reversal"]["status"] == (
        "NOT_APPLICABLE_REDUNDANT_WITH_PRIMARY_MECHANISM"
    )
    assert "parameter variant" in coverage["simple_reversal"]["reason"]


def test_stage2_authority_and_failure_learning_remain_fail_closed() -> None:
    control = _load(CONTROL_PATH)
    authority = control["stage2_authority"]
    learning = control["failure_learning"]

    assert authority["requires_legitimate_stage1_survivor"] is True
    assert authority["requires_parent_integration_and_legitimate_independent_review"] is True
    assert authority["requires_this_contract_integration_and_legitimate_independent_review"] is True
    assert authority["requires_authenticated_kraken_data_and_boundary_semantics"] is True
    assert authority["requires_canonical_exact_and_semantic_rejected_memory_admission"] is True
    assert authority["retrospective_holdout_opened"] is False
    assert authority["genuine_forward_shadow_opened"] is False
    assert authority["broker_connected"] is False
    assert authority["trade_authority"] is False
    assert authority["promotion_authority"] is False
    assert authority["automatic_deep_validation_authority"] is False

    assert learning["pre_outcome_gap_classification"] == (
        "PRE_OUTCOME_SURVIVOR_CONTROL_DEFINITION_GAP"
    )
    assert learning["negative_strategy_evidence_from_this_freeze"] is False
    assert learning["family_priority_change_from_this_freeze"] is False
    assert learning["rejected_memory_write_from_this_freeze"] is False
    assert learning["future_control_failure_routes_to_issue"] == 510


def test_parent_stage1_science_is_not_modified_or_reinterpreted() -> None:
    control = _load(CONTROL_PATH)
    parent = _load(PARENT_PATH)

    assert control["purpose"]["stage1_unchanged"] is True
    assert control["purpose"]["stage2_only"] is True
    assert control["purpose"]["outcomes_opened_by_this_contract"] is False
    assert parent["screening_authority"]["screen_started"] is False
    assert parent["screening_authority"]["retrospective_holdout_opened"] is False
    assert parent["screening_authority"]["genuine_forward_shadow_opened"] is False
    assert parent["screening_authority"]["trade_authority"] is False
    assert parent["screening_authority"]["promotion_authority"] is False

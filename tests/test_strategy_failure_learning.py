from __future__ import annotations

import copy

import pytest

from orchestration.strategy_failure_learning import (
    FAILURE_ASSET_TIMEFRAME,
    FAILURE_CAPACITY,
    FAILURE_COST_ERASED_EDGE,
    FAILURE_DATA,
    FAILURE_DUPLICATE,
    FAILURE_NO_GROSS_EDGE,
    FAILURE_REGIME_INSTABILITY,
    FAILURE_TAIL,
    FAILURE_UNDERPOWERED,
    build_failure_learning_artifact,
    classify_failure,
)
from orchestration.strategy_predeclaration import freeze_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-TEST-MOMENTUM-001",
        "fingerprint_id": "DISC-TEST-MOMENTUM-001-v1",
        "family": "test_momentum",
        "economic_mechanism": "Persistent spot-led order flow can continue after a completed impulse.",
        "hypothesis": "A frozen spot-led continuation rule has positive after-cost validation expectancy.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-20T20:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
            "historical_universe": "fixed_predeclared_assets",
        },
        "signal_rules": {
            "shock_definition": "frozen before outcomes",
            "entry_condition": "frozen before outcomes",
        },
        "execution_rules": {
            "entry_delay_bars": 1,
            "exit_rule": "fixed_holding_window",
            "position_overlap": "forbidden",
        },
        "cost_model": {
            "fees_bps": 8,
            "spread_bps": 4,
            "slippage_bps": 8,
            "funding_bps_per_day": 2,
            "stress_multipliers": [1.0, 2.0, 3.0],
        },
        "search_plan": {
            "multiple_testing_family_id": "MTF-TEST-MOM-001",
            "planned_hypothesis_count": 4,
            "planned_parameter_variants": 1,
        },
        "validation_plan": {
            "chronological": True,
            "selection_uses_training_and_validation_only": True,
            "untouched_oos_required": True,
            "genuine_forward_required": True,
        },
        "protected_evidence": {
            "untouched_oos_opened": False,
            "genuine_forward_opened": False,
        },
        "failure_learning_plan": {
            "minimum_validation_trades": 20,
            "minimum_cell_trades": 8,
            "minimum_stable_cell_fraction": 0.67,
            "catastrophic_event_loss_bps": 500,
            "max_winner_concentration_share": 0.50,
            "require_positive_validation_halves": True,
        },
    }


def _frozen() -> dict:
    return freeze_predeclaration(_candidate(), rejected_entries=[])


def _validation_window() -> dict:
    return {
        "start_utc": "2026-08-01T00:00:00+00:00",
        "end_utc": "2026-08-31T00:00:00+00:00",
        "half_windows": [
            {
                "start_utc": "2026-08-01T00:00:00+00:00",
                "end_utc": "2026-08-16T00:00:00+00:00",
            },
            {
                "start_utc": "2026-08-16T00:00:00+00:00",
                "end_utc": "2026-08-31T00:00:00+00:00",
            },
        ],
    }


def _screen(parent: dict | None = None) -> dict:
    parent = parent or _frozen()
    return {
        "schema_version": 1,
        "fingerprint_id": parent["fingerprint_id"],
        "contract_sha256": parent["contract_sha256"],
        "screen_id": "SCREEN-TEST-001",
        "screen_cutoff": "2026-09-20T21:00:00+00:00",
        "validation_window": _validation_window(),
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "data_quality": {
            "chronology_pass": True,
            "point_in_time_pass": True,
            "data_contract_pass": True,
        },
        "validation": {
            "trades": 40,
            "gross_mean_bps": 40,
            "net_mean_bps": 20,
            "profit_factor": 1.30,
            "half_net_bps": [18, 22],
        },
        "cost_stress": [
            {"multiplier": 1.0, "net_mean_bps": 20},
            {"multiplier": 2.0, "net_mean_bps": 10},
            {"multiplier": 3.0, "net_mean_bps": 4},
        ],
        "risk": {
            "worst_event_net_bps": -120,
            "winner_concentration_share": 0.25,
            "without_best_net_mean_bps": 15,
        },
        "asset_timeframe_cells": [
            {"market": "BTC-USDC", "timeframe": "1h", "trades": 20, "net_mean_bps": 18},
            {"market": "ETH-USDC", "timeframe": "1h", "trades": 20, "net_mean_bps": 22},
        ],
        "regime_cells": [
            {"label": "high_vol", "trades": 20, "net_mean_bps": 18},
            {"label": "low_vol", "trades": 20, "net_mean_bps": 22},
        ],
        "capacity": {"liquidity_capacity_pass": True},
    }


def _rejection(fingerprint: str = "DISC-OLD-001-v1") -> dict:
    return {
        "fingerprint_id": fingerprint,
        "fingerprint_version": 1,
        "hypothesis": "old",
        "economic_mechanism": "old",
        "horizons_evaluated": ["1h"],
        "sample_sizes": {"n": 20},
        "rejection_evidence": {"x": 1},
        "rejection_reason": "failed",
        "rejection_date": "2026-09-20",
        "do_not_resubmit_same_fingerprint": True,
        "reconsideration_conditions": "new mechanism only",
    }


def test_clean_screen_pass_is_research_only():
    parent = _frozen()
    result = classify_failure(parent, _screen(parent), rejected_entries=[])
    assert result == {
        "status": "SCREEN_PASS",
        "failure_categories": [],
        "rejection_eligible": False,
        "protected_evidence_opened": False,
    }


def test_no_gross_edge_and_cost_erased_edge_are_distinct():
    parent = _frozen()
    no_edge = _screen(parent)
    no_edge["validation"]["gross_mean_bps"] = -1
    no_edge["validation"]["net_mean_bps"] = -20
    assert FAILURE_NO_GROSS_EDGE in classify_failure(parent, no_edge, rejected_entries=[])["failure_categories"]

    cost_erased = _screen(parent)
    cost_erased["validation"]["gross_mean_bps"] = 25
    cost_erased["validation"]["net_mean_bps"] = -2
    cost_erased["cost_stress"][0]["net_mean_bps"] = -2
    result = classify_failure(parent, cost_erased, rejected_entries=[])
    assert FAILURE_COST_ERASED_EDGE in result["failure_categories"]
    assert FAILURE_NO_GROSS_EDGE not in result["failure_categories"]


def test_stress_cost_failure_is_not_hidden_by_positive_base_case():
    parent = _frozen()
    screen = _screen(parent)
    screen["cost_stress"][2]["net_mean_bps"] = -1
    result = classify_failure(parent, screen, rejected_entries=[])
    assert result["status"] == "REJECTED"
    assert FAILURE_COST_ERASED_EDGE in result["failure_categories"]


def test_underpowered_result_is_inconclusive_not_rejected():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["trades"] = 10
    result = classify_failure(parent, screen, rejected_entries=[])
    assert result["status"] == "INCONCLUSIVE"
    assert result["failure_categories"] == [FAILURE_UNDERPOWERED]
    assert result["rejection_eligible"] is False


def test_catastrophic_tail_is_immediate_veto_even_when_underpowered():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["trades"] = 10
    screen["risk"]["worst_event_net_bps"] = -600
    result = classify_failure(parent, screen, rejected_entries=[])
    assert result["status"] == "REJECTED"
    assert result["failure_categories"] == [FAILURE_TAIL]
    assert result["rejection_eligible"] is True


def test_data_or_pit_failure_stops_economic_interpretation():
    parent = _frozen()
    screen = _screen(parent)
    screen["data_quality"]["point_in_time_pass"] = False
    screen["validation"]["gross_mean_bps"] = -999
    result = classify_failure(parent, screen, rejected_entries=[])
    assert result["status"] == "INCONCLUSIVE"
    assert result["failure_categories"] == [FAILURE_DATA]


def test_regime_asset_timeframe_and_capacity_failures_are_classified():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["half_net_bps"] = [20, -5]
    screen["asset_timeframe_cells"] = [
        {"market": "BTC-USDC", "timeframe": "1h", "trades": 20, "net_mean_bps": 20},
        {"market": "ETH-USDC", "timeframe": "1h", "trades": 20, "net_mean_bps": -4},
        {"market": "SOL-USDC", "timeframe": "1h", "trades": 20, "net_mean_bps": -8},
    ]
    screen["regime_cells"] = [
        {"label": "high_vol", "trades": 20, "net_mean_bps": 30},
        {"label": "low_vol", "trades": 20, "net_mean_bps": -5},
    ]
    screen["capacity"]["liquidity_capacity_pass"] = False
    failures = set(classify_failure(parent, screen, rejected_entries=[])["failure_categories"])
    assert {FAILURE_REGIME_INSTABILITY, FAILURE_ASSET_TIMEFRAME, FAILURE_CAPACITY} <= failures


def test_rejected_semantic_duplicate_must_reference_real_negative_memory():
    parent = _frozen()
    screen = _screen(parent)
    screen["duplicate_of_rejected_fingerprint"] = "DISC-OLD-001-v1"
    result = classify_failure(parent, screen, rejected_entries=[_rejection()])
    assert result["failure_categories"] == [FAILURE_DUPLICATE]

    screen["duplicate_of_rejected_fingerprint"] = "UNKNOWN"
    with pytest.raises(RuntimeError, match="durable rejected memory"):
        classify_failure(parent, screen, rejected_entries=[_rejection()])


def test_screen_identity_and_protected_evidence_fail_closed():
    parent = _frozen()
    wrong = _screen(parent)
    wrong["contract_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="contract_sha256"):
        classify_failure(parent, wrong, rejected_entries=[])

    opened = _screen(parent)
    opened["untouched_oos_opened"] = True
    with pytest.raises(RuntimeError, match="untouched OOS"):
        classify_failure(parent, opened, rejected_entries=[])


def _successor(parent: dict, fingerprint: str, _legacy_score: tuple[float, float, float, float]) -> dict:
    child = copy.deepcopy(parent)
    child.pop("contract_sha256", None)
    child["hypothesis_id"] = fingerprint.removesuffix("-v2").removesuffix("-v1")
    child["fingerprint_id"] = fingerprint
    child["economic_mechanism"] = "Inventory replenishment after spot-led dislocation can produce short-horizon reversion."
    child["hypothesis"] = "A frozen inventory-replenishment condition has positive after-cost expectancy."
    child["signal_rules"] = {
        "shock_definition": "frozen before outcomes",
        "entry_condition": "independent materially different frozen rule",
    }
    child["validation_plan"]["successor_uses_fresh_nonoverlapping_selection_window"] = True
    child["validation_plan"]["successor_selection_window"] = {
        "start_utc": "2026-09-21T00:00:00+00:00",
        "end_utc": "2026-10-01T00:00:00+00:00",
    }
    child["search_plan"]["planned_hypothesis_count"] = parent["search_plan"]["planned_hypothesis_count"] + 1
    return {
        "predeclaration": child,
        "change_dimensions": ["economic_mechanism", "structural_component"],
        "rationale": "Test a different causal mechanism rather than tuning the failed continuation threshold.",
    }


def test_failure_artifact_keeps_materially_distinct_successors_unranked_and_deterministic():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["gross_mean_bps"] = -5
    screen["validation"]["net_mean_bps"] = -20

    first = _successor(parent, "DISC-TEST-REPLENISH-002-v2", (0.6, 0.7, 0.6, 0.4))
    second = _successor(parent, "DISC-TEST-REPLENISH-001-v2", (0.9, 0.9, 0.9, 0.2))
    first["predeclaration"]["execution_rules"]["entry_delay_bars"] = 2
    a = build_failure_learning_artifact(parent, screen, [first, second], rejected_entries=[])
    b = build_failure_learning_artifact(parent, screen, [first, second], rejected_entries=[])

    assert a["artifact_sha256"] == b["artifact_sha256"]
    assert [row["predeclaration"]["fingerprint_id"] for row in a["successors"]] == [
        "DISC-TEST-REPLENISH-001-v2",
        "DISC-TEST-REPLENISH-002-v2",
    ]
    assert all(row["eligibility"] == "ELIGIBLE_UNRANKED" for row in a["successors"])
    assert all("rank" not in row and "rank_score" not in row for row in a["successors"])
    assert a["successor_ranking_authority"] is False
    assert a["successor_allocation_authority"] is False
    assert a["successor_allocation_owner"] == "ISSUE_517"
    assert a["research_only"] is True
    assert a["trade_authority"] is False
    assert a["untouched_oos_opened"] is False


def test_unchanged_or_same_fingerprint_successor_is_rejected():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["gross_mean_bps"] = -5
    screen["validation"]["net_mean_bps"] = -20

    unchanged = copy.deepcopy(parent)
    unchanged.pop("contract_sha256", None)
    unchanged["validation_plan"]["successor_uses_fresh_nonoverlapping_selection_window"] = True
    unchanged["validation_plan"]["successor_selection_window"] = {
        "start_utc": "2026-09-21T00:00:00+00:00",
        "end_utc": "2026-10-01T00:00:00+00:00",
    }
    unchanged["search_plan"]["planned_hypothesis_count"] += 1
    proposal = {
        "predeclaration": unchanged,
        "change_dimensions": ["economic_mechanism"],
        "rationale": "rename",
    }
    with pytest.raises(RuntimeError, match="reuse the failed parent fingerprint"):
        build_failure_learning_artifact(parent, screen, [proposal], rejected_entries=[])


def test_new_family_successor_must_preserve_parent_multiple_testing_ancestry():
    parent = _frozen()
    screen = _screen(parent)
    screen["validation"]["gross_mean_bps"] = -5
    screen["validation"]["net_mean_bps"] = -20

    proposal = _successor(parent, "DISC-TEST-REPLENISH-003-v2", (0.8, 0.8, 0.8, 0.2))
    proposal["predeclaration"]["search_plan"]["multiple_testing_family_id"] = "MTF-NEW-001"
    proposal["predeclaration"]["search_plan"]["planned_hypothesis_count"] = 1
    with pytest.raises(RuntimeError, match="parent_multiple_testing_family_id"):
        build_failure_learning_artifact(parent, screen, [proposal], rejected_entries=[])

    proposal["predeclaration"]["search_plan"]["parent_multiple_testing_family_id"] = parent["search_plan"]["multiple_testing_family_id"]
    artifact = build_failure_learning_artifact(parent, screen, [proposal], rejected_entries=[])
    assert artifact["successors"][0]["predeclaration"]["search_plan"]["parent_multiple_testing_family_id"] == "MTF-TEST-MOM-001"


def test_passed_screen_cannot_spawn_failure_successors():
    parent = _frozen()
    with pytest.raises(RuntimeError, match="only valid after"):
        build_failure_learning_artifact(
            parent,
            _screen(parent),
            [_successor(parent, "DISC-TEST-REPLENISH-004-v2", (0.8, 0.8, 0.8, 0.2))],
            rejected_entries=[],
        )


def test_tampering_with_frozen_failure_thresholds_breaks_contract():
    parent = _frozen()
    parent["failure_learning_plan"]["minimum_validation_trades"] = 2
    with pytest.raises(RuntimeError, match="contract_sha256"):
        classify_failure(parent, _screen(_frozen()), rejected_entries=[])

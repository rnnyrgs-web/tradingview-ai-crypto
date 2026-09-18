import copy

import pytest

from acc002_evidence_contract import (
    build_dataset_manifest,
    declared_search_contract,
    selection_predicate_details,
    split_timestamp_boundaries,
)


def _rows(start=1_000, count=3):
    return [
        {
            "ts": start + i * 60_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 10.0 + i,
            "quote_volume": 1000.0 + i,
        }
        for i in range(count)
    ]


def _segment(*, samples=30, rank_ic=0.1, worst_net=0.01, positive_rate=0.6):
    return {
        "timestamps": samples,
        "mean_rank_ic": rank_ic,
        "cost_stress": {
            "1.0": {
                "mean_net_top_minus_bottom": worst_net + 0.01,
                "positive_net_spread_rate": 0.7,
            },
            "3.0": {
                "mean_net_top_minus_bottom": worst_net,
                "positive_net_spread_rate": positive_rate,
            },
        },
    }


def test_dataset_manifest_hash_is_stable_and_binds_exact_rows_and_rank_order():
    histories = {"BTC-USDT": _rows(), "ETH-USDT": _rows(start=2_000)}
    manifest = build_dataset_manifest(
        histories,
        ranked_symbols=["BTC-USDT", "ETH-USDT", "MISSING-USDT"],
        bar="1H",
        source_by_symbol={"BTC-USDT": "OKX", "ETH-USDT": "OKX"},
        point_in_time_universe={
            "survivorship_safe": False,
            "promotion_allowed": False,
            "reason": "current_survivor_universe_only",
        },
    )
    same = build_dataset_manifest(
        {"ETH-USDT": copy.deepcopy(histories["ETH-USDT"]), "BTC-USDT": copy.deepcopy(histories["BTC-USDT"])},
        ranked_symbols=["BTC-USDT", "ETH-USDT", "MISSING-USDT"],
        bar="1H",
        source_by_symbol={"ETH-USDT": "OKX", "BTC-USDT": "OKX"},
        point_in_time_universe={
            "survivorship_safe": False,
            "promotion_allowed": False,
            "reason": "current_survivor_universe_only",
        },
    )
    assert manifest["dataset_sha256"] == same["dataset_sha256"]
    assert manifest["scored_symbols"] == ["BTC-USDT", "ETH-USDT"]
    assert manifest["missing_ranked_symbols"] == ["MISSING-USDT"]
    assert manifest["per_symbol"]["BTC-USDT"]["first_ts"] == histories["BTC-USDT"][0]["ts"]
    assert manifest["per_symbol"]["BTC-USDT"]["last_ts"] == histories["BTC-USDT"][-1]["ts"]
    assert manifest["survivorship_safe"] is False
    assert manifest["promotion_allowed_from_dataset_provenance"] is False
    assert manifest["trade_authority"] is False

    changed = copy.deepcopy(histories)
    changed["BTC-USDT"][1]["close"] += 0.01
    changed_manifest = build_dataset_manifest(
        changed,
        ranked_symbols=["BTC-USDT", "ETH-USDT", "MISSING-USDT"],
        bar="1H",
    )
    assert changed_manifest["dataset_sha256"] != manifest["dataset_sha256"]

    reordered = build_dataset_manifest(
        histories,
        ranked_symbols=["ETH-USDT", "BTC-USDT", "MISSING-USDT"],
        bar="1H",
    )
    assert reordered["dataset_sha256"] != manifest["dataset_sha256"]


def test_dataset_manifest_rejects_nonchronological_or_incomplete_rows():
    bad = _rows()
    bad[1]["ts"] = bad[0]["ts"]
    with pytest.raises(ValueError, match="strictly increasing"):
        build_dataset_manifest({"BTC-USDT": bad}, ranked_symbols=["BTC-USDT"], bar="1H")

    incomplete = _rows()
    incomplete[0].pop("quote_volume")
    with pytest.raises(ValueError, match="required normalized fields"):
        build_dataset_manifest({"BTC-USDT": incomplete}, ranked_symbols=["BTC-USDT"], bar="1H")


def test_split_timestamp_boundaries_exposes_train_validation_and_locked_oos_dates_without_scoring():
    panel = [{"ts": 10_000 + i * 1_000, "rows": []} for i in range(10)]
    boundaries = split_timestamp_boundaries(
        panel,
        {
            "train": (0, 4),
            "validation": (5, 7),
            "untouched_oos": (8, 10),
        },
    )
    assert boundaries["train"] == {
        "start_index": 0,
        "end_index_exclusive": 4,
        "first_ts": 10_000,
        "last_ts": 13_000,
        "raw_observations": 4,
    }
    assert boundaries["validation"]["first_ts"] == 15_000
    assert boundaries["untouched_oos"]["first_ts"] == 18_000
    assert boundaries["untouched_oos"]["last_ts"] == 19_000


def test_selection_predicate_details_surfaces_full_failure_including_positive_rate():
    pre = {
        "train": _segment(),
        "validation": _segment(positive_rate=0.49),
    }
    details = selection_predicate_details(pre)
    assert details["passes_all"] is False
    assert details["failure_reasons"] == ["validation_max_cost_positive_net_spread_rate"]
    rate = details["requirements"]["validation_max_cost_positive_net_spread_rate"]
    assert rate["value"] == 0.49
    assert rate["threshold"] == 0.50
    assert rate["cost_multiplier"] == 3.0
    assert details["trade_authority"] is False


def test_selection_predicate_details_matches_all_pass_case():
    details = selection_predicate_details({"train": _segment(), "validation": _segment()})
    assert details["passes_all"] is True
    assert details["failure_reasons"] == []


def test_declared_search_contract_freezes_screen_breadth_before_outcomes():
    contract = declared_search_contract(
        lookback_grid=((4, 16, 64), (6, 24, 72), (8, 32, 96)),
        liquidity_subsets=(15, 30, 45),
        minimum_passing_liquidity_subsets=2,
        minimum_stable_candidates=2,
        cost_stress_multipliers=(1.0, 1.5, 2.0, 3.0),
    )
    assert contract["candidate_configuration_count"] == 3
    assert contract["liquidity_subset_count"] == 3
    assert contract["declared_pre_oos_candidate_subset_evaluations"] == 9
    assert contract["adaptive_parameter_search"] is False
    assert contract["untouched_oos_available_for_selection"] is False
    assert contract["trade_authority"] is False

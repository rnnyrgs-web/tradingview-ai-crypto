import hashlib
import json
from pathlib import Path

from strategy_discovery_supervisor import load_queue, snapshot


CONTRACT_PATH = Path("orchestration/disc_btc_leadlag_001.json")
QUEUE_PATH = Path("orchestration/strategy_discovery_queue.json")
SOURCE_EVIDENCE_PATH = Path("orchestration/evidence/disc_liquidity_meanrev_001_20260919.json")
SOURCE_DATASET_PATH = Path("orchestration/evidence/liquidity_meanrev_001_cache/dataset.json.gz")


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _contract_sha256(contract):
    payload = {
        key: value
        for key, value in contract.items()
        if key not in {"contract_sha256", "contract_fingerprint_definition"}
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_contract_is_frozen_before_returns_and_keeps_protected_evidence_closed():
    contract = _contract()
    assert contract["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert contract["status"] == "PREDECLARED_SELECTION_ONLY"
    assert contract["provenance"]["contract_frozen_before_candidate_returns"] is True
    assert contract["provenance"]["candidate_returns_inspected"] is False
    assert contract["chronology"]["untouched_oos"] == "LOCKED"
    assert contract["provenance"]["untouched_oos_opened"] is False
    assert contract["provenance"]["genuine_forward_opened"] is False
    assert contract["trade_authority"] is False
    assert contract["promotion_authority"] is False
    assert contract["contract_sha256"] == _contract_sha256(contract)


def test_fixed_leader_followers_and_data_identity_cannot_be_winner_selected():
    contract = _contract()
    source = contract["source"]
    breadth = contract["search_breadth"]
    assert source["leader_instrument"] == "BTC-USDT-SWAP"
    assert source["fixed_follower_instruments"] == ["ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    assert source["asset_substitution_allowed"] is False
    assert breadth["mandatory_replication_followers"] == 2
    assert breadth["asset_or_timeframe_winner_selection_allowed"] is False
    assert breadth["parameter_optimization_allowed"] is False
    assert contract["pre_oos_pass_rule"]["minimum_passing_followers"] == 2


def test_signal_is_strictly_past_based_and_incremental_to_frozen_baseline():
    contract = _contract()
    rule = contract["primary_rule"]
    assert rule["trailing_window_bars"] == 168
    assert "t-168..t-1" in rule["follower_beta_definition"]
    assert "signal-bar returns excluded" in rule["follower_beta_definition"]
    assert rule["decision_timestamp"].startswith("close of completed aligned signal bar")
    assert rule["entry"].startswith("follower open at aligned bar t+1")
    assert rule["exit"].startswith("follower open at aligned bar t+7")
    assert "omit follower beta" in contract["baseline"]["rule"]
    assert contract["costs"]["stress_multipliers"][-1] == 3.0


def test_beta_estimator_is_unambiguously_through_origin_and_fail_closed():
    estimator = _contract()["primary_rule"]["follower_beta_estimator"]
    assert estimator == {
        "type": "OLS_THROUGH_ORIGIN",
        "formula": "sum(btc_return_i * follower_return_i) / sum(btc_return_i ** 2)",
        "window": "168 aligned completed returns t-168..t-1",
        "centering": "NONE",
        "intercept": 0,
        "signal_bar_excluded": True,
        "zero_denominator_policy": "NO_TRADE",
    }


def test_portfolio_economics_can_reconcile_trade_cost_and_hourly_nav_evidence():
    contract = _contract()
    economics = contract["portfolio_economics"]
    assert economics["initial_capital_usd"] == 100000
    assert economics["per_position_nav_fraction"] == 0.25
    assert economics["max_concurrent_positions"] == 2
    assert economics["max_gross_exposure_nav_fraction"] == 0.5
    assert economics["gross_exposure_definition"] == (
        "sum of absolute point-in-time marked position values"
    )
    assert economics["capacity_policy"] == (
        "NO_TRADE when the full 25% NAV entry would breach either cap; never resize"
    )
    assert economics["leverage"] == 1.0
    assert economics["external_cash_flows_allowed"] is False
    assert economics["common_event_id_definition"] == (
        "BTC-USDT-SWAP|signal_bar_close_utc|BTC_direction"
    )
    assert economics["same_btc_event_shared_across_followers"] is True
    assert economics["nav_marking"]["frequency"] == "EVERY_ALIGNED_COMPLETED_HOUR"
    assert economics["nav_marking"]["open_positions"] == "LATEST_POINT_IN_TIME_CLOSE"
    assert economics["short_collateral"]["convention"] == "FULLY_COLLATERALIZED_LINEAR_1X"
    assert economics["required_profitability_learning_artifacts"] == [
        "versioned_contract",
        "trade_records",
        "hourly_reconciled_nav",
        "analysis",
    ]
    costs = contract["costs"]["base_component_bps_round_trip"]
    assert costs == {"fees": 10, "spread": 4, "slippage": 4, "funding_carry": 2}
    assert sum(costs.values()) == contract["costs"]["base_round_trip_bps"]
    assert contract["costs"]["nav_debit_timing"] == {
        "entry": "one half of fees, spread and slippage",
        "exit": "remaining half of fees, spread and slippage plus all funding_carry",
    }


def test_reused_development_history_is_not_fresh_confirmation_evidence():
    reuse = _contract()["sequential_reuse_control"]
    assert reuse["dataset_reused_by_prior_primary_fingerprints"] == [
        "DISC-LIQUIDITY-MEANREV-001-v1"
    ]
    assert reuse["cumulative_primary_trial_index_on_dataset"] == 2
    assert reuse["reused_train_validation_classification"] == (
        "EXPLORATORY_DEVELOPMENT_ONLY"
    )
    assert reuse["reused_history_can_support_promotion"] is False
    assert reuse["fresh_confirmation"]["evidence_class"] == "GENUINE_FORWARD"
    assert reuse["fresh_confirmation"]["start_strictly_after_utc"] == (
        "2026-09-19T03:00:00+00:00"
    )
    assert reuse["fresh_confirmation"]["minimum_independent_btc_events"] == 20
    assert reuse["fresh_confirmation"]["minimum_completed_trades_per_follower"] == 8


def test_verified_source_metadata_and_immutable_dataset_are_present():
    contract = _contract()
    evidence = json.loads(SOURCE_EVIDENCE_PATH.read_text(encoding="utf-8"))
    dataset = evidence["dataset"]
    assert SOURCE_DATASET_PATH.is_file()
    assert dataset["data_integrity_ok"] is True
    assert dataset["fixed_instruments"] == contract["source"]["required_instruments"]
    assert dataset["normalized_rows_sha256"] == contract["source"]["normalized_rows_sha256"]
    assert dataset["normalized_row_count"] == contract["source"]["normalized_row_count"]
    assert dataset["coverage_start_utc"] == contract["source"]["coverage_start_utc"]
    assert dataset["coverage_end_utc"] == contract["source"]["coverage_end_utc"]


def test_queue_does_not_expose_terminally_rejected_candidate():
    queue = load_queue(QUEUE_PATH)
    state = snapshot(queue)
    assert state["ranked_cheap_screens"] == []
    assert state["next_action"] is None
    assert all(
        row["fingerprint_id"] != "DISC-BTC-LEADLAG-001-v1"
        for row in queue["candidates"]
    )
    assert state["active_deep_candidate"] is None
    assert state["trade_authority"] is False

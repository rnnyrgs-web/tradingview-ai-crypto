import copy

import pytest

from forward_proof import build_forward_decision_record, assert_forward_provenance_unchanged
from strategy_contract import freeze_strategy_contract


def frozen_contract():
    return freeze_strategy_contract({
        "strategy_family": "momentum",
        "strategy_version": "v1",
        "features": {"residual_momentum": {"lookback": 24}},
        "universe": ["BTC", "ETH"],
        "universe_selection_rules": {"top_n": 2},
        "entry_rules": {"rank_lte": 1},
        "exit_rules": {"horizon_hours": 24},
        "stop_rules": {"max_loss_pct": 2.0},
        "position_sizing": {"equal_weight": True},
        "holding_logic": {"max_hours": 24},
        "timeframes": ["1h"],
        "horizon": "24h",
        "costs": {"fees_bps": 20, "spread_bps": 4, "slippage_bps": 6, "funding_bps": 0, "execution_delay_bars": 1},
        "train_range": ["2024-01-01", "2024-12-31"],
        "validation_range": ["2025-01-01", "2025-06-30"],
        "untouched_oos_range": ["2025-07-01", "2025-12-31"],
        "git_sha": "abc123",
        "research_code_sha256": "code-sha",
        "dataset_id": "kraken-1h-v1",
        "dataset_sha256": "data-sha",
        "hypothesis_id": "H-001",
        "experiment_id": "EXP-001",
    })


def forward_gate():
    return {
        "state": "FORWARD_PENDING",
        "blocking_gates": ["genuine_forward"],
        "production_candidate": False,
        "real_money_trade_authority": False,
    }


def test_forward_record_requires_independent_reproduction_gate_to_have_passed():
    with pytest.raises(RuntimeError, match="FORWARD_PENDING"):
        build_forward_decision_record(
            frozen_contract(),
            {"state": "OOS_PASS", "blocking_gates": ["independent_reproduction"], "real_money_trade_authority": False},
            signal_id="SIG-001",
            decision_timestamp="2026-09-16T12:00:00+00:00",
            symbol="BTC",
            direction="LONG",
            entry_reference=60000.0,
            expected_horizon="24h",
            expected_move_pct=2.0,
            stop_rule="2pct",
            exit_rule="24h",
        )


def test_forward_record_binds_immutable_strategy_experiment_code_and_data_identity():
    frozen = frozen_contract()
    record = build_forward_decision_record(
        frozen,
        forward_gate(),
        signal_id="SIG-001",
        decision_timestamp="2026-09-16T12:00:00+00:00",
        symbol="BTC",
        direction="LONG",
        entry_reference=60000.0,
        expected_horizon="24h",
        expected_move_pct=2.0,
        stop_rule="2pct",
        exit_rule="24h",
    )
    assert record["strategy_fingerprint"] == frozen["fingerprint"]
    assert record["experiment_id"] == "EXP-001"
    assert record["git_sha"] == "abc123"
    assert record["dataset_sha256"] == "data-sha"
    assert record["real_money_trade_authority"] is False


def test_forward_provenance_cannot_be_rewritten_but_outcome_can_be_appended():
    record = build_forward_decision_record(
        frozen_contract(), forward_gate(), signal_id="SIG-001",
        decision_timestamp="2026-09-16T12:00:00+00:00", symbol="BTC", direction="LONG",
        entry_reference=60000.0, expected_horizon="24h", expected_move_pct=2.0,
        stop_rule="2pct", exit_rule="24h",
    )
    outcome = copy.deepcopy(record)
    outcome["actual_return_pct"] = 1.2
    assert_forward_provenance_unchanged(record, outcome)
    tampered = copy.deepcopy(outcome)
    tampered["dataset_sha256"] = "different-data"
    with pytest.raises(RuntimeError, match="forward provenance changed"):
        assert_forward_provenance_unchanged(record, tampered)

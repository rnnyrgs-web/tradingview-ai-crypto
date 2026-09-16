import pytest

from strategy_contract import StrategyContract, assert_contract_unchanged, freeze_strategy_contract


def base_payload():
    return {
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
        "costs": {
            "fees_bps": 20,
            "spread_bps": 4,
            "slippage_bps": 6,
            "funding_bps": 0,
            "execution_delay_bars": 1,
        },
        "train_range": ["2024-01-01", "2024-12-31"],
        "validation_range": ["2025-01-01", "2025-06-30"],
        "untouched_oos_range": ["2025-07-01", "2025-12-31"],
        "git_sha": "abc123",
        "research_code_sha256": "code-sha",
        "dataset_id": "kraken-1h-v1",
        "dataset_sha256": "data-sha",
        "hypothesis_id": "H-001",
        "experiment_id": "EXP-001",
    }


def test_contract_fingerprint_is_deterministic():
    payload = base_payload()
    reversed_payload = dict(reversed(list(payload.items())))
    assert StrategyContract.from_mapping(payload).fingerprint() == StrategyContract.from_mapping(reversed_payload).fingerprint()


def test_contract_fingerprint_changes_for_material_rule_change():
    original = StrategyContract.from_mapping(base_payload()).fingerprint()
    changed = base_payload()
    changed["stop_rules"] = {"max_loss_pct": 2.5}
    assert StrategyContract.from_mapping(changed).fingerprint() != original


def test_frozen_contract_rejects_mutation():
    frozen = freeze_strategy_contract(base_payload())
    proposed = base_payload()
    proposed["entry_rules"] = {"rank_lte": 2}
    with pytest.raises(RuntimeError, match="immutable strategy contract changed"):
        assert_contract_unchanged(frozen, proposed)


def test_contract_rejects_missing_required_identity():
    payload = base_payload()
    payload["dataset_sha256"] = ""
    with pytest.raises(ValueError, match="dataset_sha256"):
        StrategyContract.from_mapping(payload)

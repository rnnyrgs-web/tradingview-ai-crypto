from strategy_contract import StrategyContract
from strategy_identity import build_strategy_identity


def contract_payload():
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
    }


def test_identity_uses_full_contract_fingerprint_when_supplied():
    payload = contract_payload()
    identity = build_strategy_identity("BTC", "24h", "momentum", contract=payload)
    assert identity["identity_complete"] is True
    assert identity["fingerprint"] == StrategyContract.from_mapping(payload).fingerprint()
    assert identity["contract_schema_version"] == 1

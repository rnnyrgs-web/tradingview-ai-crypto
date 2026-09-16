from research_artifact import seal_research_payload, verify_research_envelope
from research_experiment_factory import build_experiment_queue
from strategy_contract import StrategyContract


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


def test_sealed_research_payload_binds_frozen_contract():
    contract = contract_payload()
    envelope = seal_research_payload({"result": "candidate"}, strategy_contract=contract)
    expected = StrategyContract.from_mapping(contract).fingerprint()
    assert envelope["schema_version"] == 3
    assert envelope["payload"]["strategy_fingerprint"] == expected
    assert envelope["payload"]["strategy_contract"]["frozen"] is True
    assert verify_research_envelope(envelope) is True


def test_contract_tampering_breaks_research_envelope():
    envelope = seal_research_payload({"result": "candidate"}, strategy_contract=contract_payload())
    envelope["payload"]["strategy_contract"]["payload"]["stop_rules"] = {"max_loss_pct": 99}
    assert verify_research_envelope(envelope) is False


def test_experiment_factory_carries_frozen_strategy_identity_when_predeclared():
    contract = contract_payload()
    diagnostics = {
        "research_priorities": [{
            "dimension": "economic_mechanism",
            "group": "residual_momentum",
            "research_question": "Does residual momentum survive costs?",
            "requires_new_validation": True,
            "target_horizon": "24h",
            "strategy_contract": contract,
            "economic_harm_score_pct": 1.0,
            "wrong_rate": 0.4,
            "independent_samples": 30,
        }]
    }
    queue = build_experiment_queue(diagnostics, memory={"lessons": []})
    experiment = queue["experiments"][0]
    assert experiment["strategy_fingerprint"] == StrategyContract.from_mapping(contract).fingerprint()
    assert experiment["strategy_contract"]["frozen"] is True
    assert experiment["contract_frozen"] is True

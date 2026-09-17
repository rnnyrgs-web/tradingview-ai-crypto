from __future__ import annotations

import os

import pytest

from dataset_certification import certify_dataset_manifest
from research_runner import _canonical_candidate_evidence, active_strategy_contract
from strategy_contract import StrategyContract


def _manifest() -> dict:
    return {
        "dataset_id": "deep-dataset-v1",
        "source": "okx",
        "venue": "spot",
        "symbol": "BTC-USDT",
        "timezone": "UTC",
        "start_timestamp": "2025-01-01T00:00:00+00:00",
        "end_timestamp": "2025-12-31T23:00:00+00:00",
        "fields": ["open", "high", "low", "close", "volume"],
        "missing_periods": [],
        "duplicate_timestamps": 0,
        "out_of_order_records": 0,
        "impossible_ohlc_records": 0,
        "stale_records": 0,
        "future_universe_membership": False,
        "future_feature_use": False,
        "point_in_time_universe": True,
        "content_sha256": "content-sha",
    }


def _objective() -> dict:
    manifest = _manifest()
    certification = certify_dataset_manifest(manifest)
    contract = {
        "strategy_family": "momentum",
        "strategy_version": "v1",
        "features": {"momentum": {"scale": 1.0}},
        "universe": ["BTC-USDT"],
        "universe_selection_rules": {"point_in_time": True},
        "entry_rules": {"mode": "predeclared"},
        "exit_rules": {"mode": "predeclared"},
        "stop_rules": {"mode": "predeclared"},
        "position_sizing": {"mode": "equal_risk"},
        "holding_logic": {"max_bars": 24},
        "timeframes": ["1H"],
        "horizon": "24h",
        "costs": {"fees_bps": 6, "spread_bps": 2, "slippage_bps": 4, "funding_bps": 0, "execution_delay_bars": 1},
        "train_range": ["2025-01-01", "2025-06-30"],
        "validation_range": ["2025-07-01", "2025-09-30"],
        "untouched_oos_range": ["2025-10-01", "2025-12-31"],
        "git_sha": "abc123",
        "research_code_sha256": "code-sha",
        "dataset_id": certification["dataset_id"],
        "dataset_sha256": certification["dataset_sha256"],
        "hypothesis_id": "H-001",
        "experiment_id": "EXP-001",
    }
    fingerprint = StrategyContract.from_mapping(contract).fingerprint()
    return {
        "single_strategy_focus": {
            "lifecycle_phase": "DEEP_VALIDATION",
            "active_candidate": {
                "fingerprint_id": fingerprint,
                "strategy_contract": contract,
                "dataset_manifest": manifest,
                "deep_worker_contracts": {"major-btc": {"strategy_family": "momentum"}},
            },
        }
    }


def test_deep_runner_loads_exact_objective_contract(monkeypatch):
    objective = _objective()
    candidate = objective["single_strategy_focus"]["active_candidate"]
    monkeypatch.setenv("SINGLE_STRATEGY_DEEP_MODE", "1")
    monkeypatch.setenv("ACTIVE_STRATEGY_FINGERPRINT", candidate["fingerprint_id"])
    monkeypatch.setenv("ACTIVE_STRATEGY_FAMILY", "momentum")

    fingerprint, families, contract, certification = active_strategy_contract(objective)
    assert fingerprint == candidate["fingerprint_id"]
    assert families == ("momentum",)
    assert contract["experiment_id"] == "EXP-001"
    assert certification["certified"] is True


def test_deep_runner_rejects_env_identity_drift(monkeypatch):
    objective = _objective()
    monkeypatch.setenv("SINGLE_STRATEGY_DEEP_MODE", "1")
    monkeypatch.setenv("ACTIVE_STRATEGY_FINGERPRINT", "wrong")
    monkeypatch.setenv("ACTIVE_STRATEGY_FAMILY", "momentum")
    with pytest.raises(RuntimeError, match="fingerprint"):
        active_strategy_contract(objective)


def test_canonical_gate_blocks_missing_robustness_instead_of_promoting():
    objective = _objective()
    candidate = objective["single_strategy_focus"]["active_candidate"]
    certification = certify_dataset_manifest(candidate["dataset_manifest"])
    strategy = {
        "strategy_family": "momentum",
        "train": {"avg_trade_pct": 0.20, "profit_factor": 1.25, "trades": 30},
        "validation": {"avg_trade_pct": 0.12, "profit_factor": 1.15, "trades": 15},
        "holdout_test": {"avg_trade_pct": 0.10, "profit_factor": 1.12, "trades": 12},
        "robustness": {"parameter_stability": {"passed": True}},
        "multiple_testing_gate": {"passed": True},
    }
    result = _canonical_candidate_evidence(strategy, certification, oos_opened=True)
    assert result["decision"]["state"] == "VALIDATION_PASS"
    assert "robustness" in result["decision"]["blocking_gates"]
    assert result["decision"]["real_money_trade_authority"] is False


def test_canonical_gate_rejects_negative_untouched_oos():
    objective = _objective()
    candidate = objective["single_strategy_focus"]["active_candidate"]
    certification = certify_dataset_manifest(candidate["dataset_manifest"])
    strategy = {
        "strategy_family": "momentum",
        "train": {"avg_trade_pct": 0.20, "profit_factor": 1.25, "trades": 30},
        "validation": {"avg_trade_pct": 0.12, "profit_factor": 1.15, "trades": 15},
        "holdout_test": {"avg_trade_pct": -0.01, "profit_factor": 0.98, "trades": 12},
        "robustness": {"parameter_stability": {"passed": True}},
        "multiple_testing_gate": {"passed": True},
    }
    result = _canonical_candidate_evidence(strategy, certification, oos_opened=True)
    assert result["decision"]["state"] == "REJECTED"
    assert "oos_economics_failed" in result["decision"]["rejection_reasons"]

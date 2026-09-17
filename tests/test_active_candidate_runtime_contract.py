from __future__ import annotations

import copy

import pytest

from dataset_certification import certify_dataset_manifest
from signal_development import ObjectiveError, validate_active_candidate_contract
from strategy_contract import StrategyContract


def _manifest() -> dict:
    return {
        "dataset_id": "acc002-24h-frozen-v1",
        "source": "okx",
        "venue": "spot",
        "symbol": "MULTI_ASSET",
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
        "content_sha256": "content-sha-001",
    }


def _candidate() -> dict:
    manifest = _manifest()
    certification = certify_dataset_manifest(manifest)
    assert certification["certified"] is True
    contract = {
        "strategy_family": "momentum",
        "strategy_version": "v1",
        "features": {"cross_asset_rank": {"lookbacks": [4, 16, 64]}},
        "universe": ["BTC-USDT", "ETH-USDT"],
        "universe_selection_rules": {"point_in_time": True, "top_n": 2},
        "entry_rules": {"rank_bucket": "top"},
        "exit_rules": {"forward_bars": 24},
        "stop_rules": {"mode": "predeclared"},
        "position_sizing": {"mode": "equal_weight"},
        "holding_logic": {"bars": 24},
        "timeframes": ["1H"],
        "horizon": "24h",
        "costs": {
            "fees_bps": 6,
            "spread_bps": 2,
            "slippage_bps": 4,
            "funding_bps": 0,
            "execution_delay_bars": 1,
        },
        "train_range": ["2025-01-01", "2025-06-30"],
        "validation_range": ["2025-07-01", "2025-09-30"],
        "untouched_oos_range": ["2025-10-01", "2025-12-31"],
        "git_sha": "abc123",
        "research_code_sha256": "code-sha",
        "dataset_id": certification["dataset_id"],
        "dataset_sha256": certification["dataset_sha256"],
        "hypothesis_id": "H-ACC002-001",
        "experiment_id": "EXP-ACC002-001",
    }
    fingerprint = StrategyContract.from_mapping(contract).fingerprint()
    return {
        "fingerprint_id": fingerprint,
        "strategy_contract": contract,
        "dataset_manifest": manifest,
        "deep_worker_contracts": {
            "cross-asset-rank-24h": {"strategy_family": "momentum"},
        },
    }


def test_active_candidate_contract_binds_certified_dataset_and_fingerprint():
    result = validate_active_candidate_contract(_candidate())
    assert result["strategy_fingerprint"] == _candidate()["fingerprint_id"]
    assert result["dataset_certification"]["certified"] is True
    assert result["strategy_contract"]["dataset_sha256"] == result["dataset_certification"]["dataset_sha256"]


def test_active_candidate_rejects_fingerprint_drift():
    candidate = _candidate()
    candidate["fingerprint_id"] = "wrong"
    with pytest.raises(ObjectiveError, match="fingerprint"):
        validate_active_candidate_contract(candidate)


def test_active_candidate_rejects_uncertified_dataset():
    candidate = _candidate()
    candidate["dataset_manifest"] = copy.deepcopy(candidate["dataset_manifest"])
    candidate["dataset_manifest"]["future_feature_use"] = True
    with pytest.raises(ObjectiveError, match="dataset"):
        validate_active_candidate_contract(candidate)


def test_active_candidate_rejects_worker_family_that_does_not_match_contract():
    candidate = _candidate()
    candidate["deep_worker_contracts"]["cross-asset-rank-24h"]["strategy_family"] = "trend"
    with pytest.raises(ObjectiveError, match="strategy family"):
        validate_active_candidate_contract(candidate)

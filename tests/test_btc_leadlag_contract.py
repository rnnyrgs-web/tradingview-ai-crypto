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


def test_queue_exposes_exactly_one_new_screenable_candidate():
    queue = load_queue(QUEUE_PATH)
    state = snapshot(queue)
    ranked = state["ranked_cheap_screens"]
    assert len(ranked) == 1
    assert ranked[0]["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert state["next_action"]["action"] == "RUN_CHEAP_DETERMINISTIC_SCREEN"
    assert state["next_action"]["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert state["active_deep_candidate"] is None
    assert state["trade_authority"] is False

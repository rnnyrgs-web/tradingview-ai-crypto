import hashlib
import json
from pathlib import Path


CONTRACT_PATH = Path("orchestration/acc003_breakout_candidate.json")
BACKLOG_PATH = Path("orchestration/priority_backlog.json")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _contract_fingerprint(contract):
    payload = dict(contract)
    payload.pop("fingerprint_sha256", None)
    payload.pop("fingerprint_definition", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_acc003_contract_fingerprint_is_self_consistent_and_backlog_bound():
    contract = _load(CONTRACT_PATH)
    backlog = _load(BACKLOG_PATH)
    acc003 = next(item for item in backlog["items"] if item["id"] == "ACC-003")

    assert contract["fingerprint_sha256"] == _contract_fingerprint(contract)
    assert acc003["selection_contract"] == CONTRACT_PATH.as_posix()
    assert acc003["selection_fingerprint_sha256"] == contract["fingerprint_sha256"]
    assert acc003["status"] == "READY"


def test_acc003_is_one_bounded_research_only_candidate_with_oos_locked():
    contract = _load(CONTRACT_PATH)

    assert contract["candidate_id"] == "ACC-003-BTCETH-COMPRESSION-BREAKOUT-24H-V1"
    assert contract["status"] == "PREDECLARED_SELECTION_ONLY"
    assert contract["research_only"] is True
    assert contract["trade_authority"] is False
    assert contract["promotion_authority"] is False
    assert contract["assets"] == ["BTC-USDT", "ETH-USDT"]
    assert contract["primary_horizon"] == "24h"
    assert contract["search_breadth"] == {
        "primary_candidate_count": 1,
        "baseline_count": 1,
        "sensitivity_falsifiers_count": 4,
        "parameter_optimization_allowed": False,
    }
    assert contract["chronology"]["untouched_oos"] == "LOCKED"
    assert contract["chronology"]["genuine_forward"] == "NOT_OPENED"
    assert contract["selection_result_policy"]["attractive_curve_can_bypass_gate"] is False
    assert all(check["selection_authority"] is False for check in contract["fixed_sensitivity_checks"])


def test_acc003_freezes_timestamp_safe_history_and_cost_stress_before_outcomes():
    contract = _load(CONTRACT_PATH)
    source = contract["source"]
    history = source["history_request"]

    assert source["venue"] == "OKX"
    assert source["bar_interval"] == "1H"
    assert source["completed_bars_only"] is True
    assert source["point_in_time_universe_required"] is False
    assert history["target_bars_per_asset"] == 50_000
    assert history["max_bars_per_asset"] == 50_000
    assert history["minimum_bars_per_asset"] == 17_520
    assert history["short_history_policy"] == "INSUFFICIENT_EVIDENCE"
    assert "never synthesize" in history["coverage_policy"]
    assert source["dataset_identity_required"] == [
        "exact_source",
        "coverage_start",
        "coverage_end",
        "normalized_row_count",
        "normalized_rows_sha256",
    ]

    assert contract["decision_schedule"]["frequency_hours"] == 24
    assert contract["decision_schedule"]["non_overlapping_outcomes"] is True
    assert contract["chronology"]["purge_hours"] == 24
    assert contract["costs"]["base_round_trip_bps"] == 12
    assert contract["costs"]["stress_round_trip_bps"] == [12, 24, 36]
    assert "funding/carry" in contract["costs"]["funding_carry_note"]


def test_rejected_acc002_is_not_still_routed_as_ready_work():
    backlog = _load(BACKLOG_PATH)
    acc002 = next(item for item in backlog["items"] if item["id"] == "ACC-002")

    assert acc002["status"] == "BLOCKED"
    assert "REJECTED AT SELECTION" in acc002["block_reason"]
    assert "untouched OOS remained locked" in acc002["block_reason"]
    assert "Do not tune, rescue, relabel, or open OOS" in acc002["block_reason"]

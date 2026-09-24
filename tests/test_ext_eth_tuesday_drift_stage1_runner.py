from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "orchestration" / "external_replication" / "eth_tuesday_drift_runner.py"
CONTRACT_PATH = ROOT / "orchestration" / "external_replication" / "ext_eth_tuesday_drift_001_stage1_execution.json"
EXPECTED_CONTRACT_SHA256 = "5c0354badb8650149907db8a7956bb97f159fe7aa9231bba790c01a923f294cf"


def _load_runner():
    spec = importlib.util.spec_from_file_location("eth_tuesday_drift_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _rows(gross_bps_by_week=None, *, omit_weeks=()):
    r = _load_runner()
    gross_bps_by_week = gross_bps_by_week or [100.0] * 68
    omitted = set(omit_weeks)
    rows = []
    week = r.SCREEN_START
    for index in range(68):
        entry = week + r.DAY
        exit_ts = entry + r.DAY
        if index not in omitted:
            entry_open = 1000.0
            exit_open = entry_open * (1.0 + gross_bps_by_week[index] / 10_000.0)
            rows.append({"ts": int(entry.timestamp() * 1000), "open": entry_open})
            rows.append({"ts": int(exit_ts.timestamp() * 1000), "open": exit_open})
        week += r.WEEK
    return sorted(rows, key=lambda row: row["ts"])


def test_execution_contract_is_self_bound_and_binds_runner_bytes():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    digest = contract.pop("artifact_sha256")
    assert digest == EXPECTED_CONTRACT_SHA256
    assert hashlib.sha256(_canonical_json(contract)).hexdigest() == EXPECTED_CONTRACT_SHA256
    assert contract["parent_artifact_sha256"] == "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"
    assert contract["dataset_sha256"] == "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
    assert contract["runner_git_blob_sha1"] == _git_blob_sha1(RUNNER_PATH.read_bytes())


def test_exact_schedule_is_68_weeks_split_34_and_34():
    r = _load_runner()
    sessions, missing = r.build_frozen_schedule(_rows())
    assert not missing
    assert len(sessions) == 68
    assert sum(s.half == "half_1" for s in sessions) == 34
    assert sum(s.half == "half_2" for s in sessions) == 34
    assert sessions[0].entry_timestamp.weekday() == 1
    assert sessions[0].exit_timestamp.weekday() == 2


def test_clean_positive_synthetic_case_survives_only_to_stage2_controls():
    r = _load_runner()
    result = r.evaluate_stage1(_rows([100.0] * 68))
    assert result["status"] == "STAGE1_SURVIVOR_ONLY"
    assert result["failure_classification"] is None
    assert all(result["gates"].values())
    assert result["authority"]["stage2_baseline_execution_allowed"] is True
    assert result["authority"]["profitability_claim_allowed"] is False
    assert result["authority"]["deep_promotion_allowed"] is False
    assert result["authority"]["protected_oos_opened"] is False
    assert result["authority"]["genuine_forward_opened"] is False
    assert result["authority"]["trade_authority"] is False


def test_positive_gross_but_cost_erased_is_rejected():
    r = _load_runner()
    result = r.evaluate_stage1(_rows([30.0] * 68))
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "COST_ERASED_EDGE"
    assert result["metrics"]["raw_gross"]["mean_gross_bps"] > 0
    assert result["metrics"]["full"]["48"]["mean_net_bps"] < 0


def test_chronological_half_instability_is_rejected():
    r = _load_runner()
    gross = [100.0] * 34 + [10.0] * 34
    result = r.evaluate_stage1(_rows(gross))
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "REGIME_OR_CHRONOLOGY_INSTABILITY"
    assert result["metrics"]["half_1_48bps"]["mean_net_bps"] > 0
    assert result["metrics"]["half_2_48bps"]["mean_net_bps"] < 0


def test_underpowered_half_is_inconclusive_not_rejected():
    r = _load_runner()
    result = r.evaluate_stage1(_rows([100.0] * 68, omit_weeks=range(10)))
    assert result["status"] == "INCONCLUSIVE_POWER"
    assert result["failure_classification"] == "INCONCLUSIVE_POWER"
    assert len(result["missing_sessions"]) == 10
    assert result["metrics"]["half_1_48bps"]["sessions"] == 24
    assert result["authority"]["stage2_baseline_execution_allowed"] is False


def test_single_winner_concentration_blocks_survival():
    r = _load_runner()
    gross = [80.0] * 67 + [4000.0]
    result = r.evaluate_stage1(_rows(gross))
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "WINNER_CONCENTRATION"
    assert result["metrics"]["full"]["48"]["max_positive_pnl_share"] > 0.5


def test_missing_required_boundary_is_explicit_and_never_filled():
    r = _load_runner()
    rows = _rows()
    first_tuesday = r.SCREEN_START + r.DAY
    rows = [row for row in rows if row["ts"] != int(first_tuesday.timestamp() * 1000)]
    sessions, missing = r.build_frozen_schedule(rows)
    assert len(sessions) == 67
    assert len(missing) == 1
    assert missing[0]["reason"] == "DATA/PIT_INCONCLUSIVE_SESSION"
    assert first_tuesday.isoformat() in missing[0]["missing_required_boundaries"]


def test_protected_tail_price_is_not_inspected_or_scored():
    r = _load_runner()
    rows = _rows()
    rows.append({"ts": int(r.PROTECTED_OOS_START.timestamp() * 1000), "open": "PROTECTED_NOT_READ"})
    result = r.evaluate_stage1(rows)
    assert result["scored_sessions"] == 68
    assert result["authority"]["protected_oos_opened"] is False


def test_duplicate_or_out_of_order_development_timestamps_fail_closed():
    r = _load_runner()
    rows = _rows()
    duplicate = list(rows)
    duplicate.insert(1, dict(rows[0]))
    with pytest.raises(ValueError, match="strictly increasing|duplicate"):
        r.evaluate_stage1(duplicate)

    reverse = list(rows)
    reverse[0], reverse[1] = reverse[1], reverse[0]
    with pytest.raises(ValueError, match="strictly increasing"):
        r.evaluate_stage1(reverse)


def test_no_gross_edge_has_deterministic_failure_classification():
    r = _load_runner()
    result = r.evaluate_stage1(_rows([-10.0] * 68))
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "NO_GROSS_EDGE"

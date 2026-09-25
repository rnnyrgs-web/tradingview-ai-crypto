from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_stage1_risk_amendment.json"
)
GUARDED_RUNNER_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "eth_tuesday_drift_stage1_guarded_runner.py"
)
EXPECTED_AMENDMENT_SHA256 = "8e13286cd6c586c98f6ade79409a243efde266b55e7f4ee57492affd97c4c2c0"
EXPECTED_GUARDED_RUNNER_BLOB = "f39e0b03064036fd7cb66174d744ec789ecd6e28"


def _base():
    from orchestration.external_replication import eth_tuesday_drift_runner

    return eth_tuesday_drift_runner


def _guarded():
    from orchestration.external_replication import eth_tuesday_drift_stage1_guarded_runner

    return eth_tuesday_drift_stage1_guarded_runner


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(data)}\0".encode() + data,
        usedforsecurity=False,
    ).hexdigest()


def _rows(gross_bps_by_week, *, omit_weeks=()):
    base = _base()
    omitted = set(omit_weeks)
    rows = []
    week = base.SCREEN_START
    for index in range(68):
        entry = week + base.DAY
        exit_ts = entry + base.DAY
        if index not in omitted:
            entry_open = 1000.0
            exit_open = entry_open * (1.0 + gross_bps_by_week[index] / 10_000.0)
            rows.append({"ts": int(entry.timestamp() * 1000), "open": entry_open})
            rows.append({"ts": int(exit_ts.timestamp() * 1000), "open": exit_open})
        week += base.WEEK
    return sorted(rows, key=lambda row: row["ts"])


def test_risk_amendment_is_self_bound_and_binds_guarded_runner_bytes():
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    digest = amendment.pop("artifact_sha256")
    assert digest == EXPECTED_AMENDMENT_SHA256
    assert hashlib.sha256(_canonical_json(amendment)).hexdigest() == EXPECTED_AMENDMENT_SHA256
    assert amendment["parent_artifact_sha256"] == "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"
    assert amendment["base_execution_contract_sha256"] == "823d7bbfbd411056358721dfb1e7f3764c7a445306f62aaa156945a6cd2ca46c"
    assert amendment["guarded_runner_git_blob_sha1"] == EXPECTED_GUARDED_RUNNER_BLOB
    assert _git_blob_sha1(GUARDED_RUNNER_PATH.read_bytes()) == EXPECTED_GUARDED_RUNNER_BLOB
    assert amendment["outcomes_read_to_form_amendment"] is False
    assert amendment["parent_predeclaration_mutated"] is False
    assert all(value is False for value in amendment["authority_locks"].values())


def test_clean_positive_case_survives_guarded_overlay_without_minting_authority():
    guarded = _guarded()
    result = guarded.evaluate_stage1_guarded(_rows([100.0] * 68))
    assert result["status"] == "STAGE1_SURVIVOR_ONLY"
    assert result["survived_stage1_economic_gates"] is True
    assert result["gates"]["catastrophic_tail_veto_48bps_both_halves"] is True
    assert result["gates"]["single_winner_dependence_veto_48bps_both_halves"] is True
    assert result["authority"]["stage2_baseline_execution_allowed"] is False
    assert result["authority"]["profitability_claim_allowed"] is False
    assert result["authority"]["deep_promotion_allowed"] is False
    assert result["authority"]["protected_oos_opened"] is False
    assert result["authority"]["trade_authority"] is False


def test_catastrophic_half_loss_cannot_hide_inside_positive_full_window():
    base = _base()
    guarded = _guarded()
    gross = [148.0] * 33 + [-1952.0] + [148.0] * 34
    rows = _rows(gross)

    unguarded = base.evaluate_stage1(rows)
    assert unguarded["status"] == "STAGE1_SURVIVOR_ONLY"
    assert unguarded["metrics"]["half_1_48bps"]["mean_net_bps"] > 0
    assert unguarded["metrics"]["full"]["72"]["mean_net_bps"] > 0

    result = guarded.evaluate_stage1_guarded(rows)
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION"
    assert "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION" in result["failure_categories"]
    assert result["risk_amendment"]["metrics"]["half_1"]["catastrophic_tail_pass"] is False
    assert result["gates"]["catastrophic_tail_veto_48bps_both_halves"] is False
    assert result["survived_stage1_economic_gates"] is False


def test_half_dependent_on_one_winner_cannot_survive_even_when_base_screen_passes():
    base = _base()
    guarded = _guarded()
    gross = [38.0] * 33 + [448.0] + [148.0] * 34
    rows = _rows(gross)

    unguarded = base.evaluate_stage1(rows)
    assert unguarded["status"] == "STAGE1_SURVIVOR_ONLY"
    assert unguarded["metrics"]["half_1_48bps"]["mean_net_bps"] > 0
    assert unguarded["metrics"]["full"]["72"]["mean_net_bps"] > 0

    result = guarded.evaluate_stage1_guarded(rows)
    half_1_risk = result["risk_amendment"]["metrics"]["half_1"]
    assert half_1_risk["catastrophic_tail_pass"] is True
    assert half_1_risk["single_winner_dependence_pass"] is False
    assert half_1_risk["without_best_mean_net_bps"] < 0
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION"
    assert result["gates"]["single_winner_dependence_veto_48bps_both_halves"] is False


def test_observed_catastrophic_risk_has_rejection_precedence_over_power_inconclusive():
    guarded = _guarded()
    gross = [148.0] * 33 + [-1952.0] + [148.0] * 34
    rows = _rows(gross, omit_weeks=range(9))
    result = guarded.evaluate_stage1_guarded(rows)
    assert result["metrics"]["half_1_48bps"]["sessions"] == 25
    # Remove one more ordinary half-1 week to make the base screen underpowered
    # while retaining the observed catastrophic event.
    rows = _rows(gross, omit_weeks=range(10))
    result = guarded.evaluate_stage1_guarded(rows)
    assert result["metrics"]["half_1_48bps"]["sessions"] == 24
    assert result["status"] == "REJECT_PRE_OOS"
    assert result["failure_classification"] == "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION"

from __future__ import annotations

from types import SimpleNamespace

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_failure_learning_adapter import (
    CERTIFIED_EVIDENCE_STATUS,
    EXECUTION_CONTRACT_SHA256,
    build_failure_learning_screen,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _summary() -> SimpleNamespace:
    return SimpleNamespace(
        independent_events=23,
        mean_24bps=0.0040,
        mean_48bps=0.0016,
        mean_72bps=-0.0008,
        profit_factor_24bps=1.40,
        leave_best_mean_24bps=0.0015,
        worst_loss_abs_24bps=0.0060,
        winner_concentration_share_24bps=0.30,
    )


def _result(*, evidence_status: str = CERTIFIED_EVIDENCE_STATUS) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id="DISC-SIGNED-VOLUME-DRIFT-001-v1",
        evidence_status=evidence_status,
        validation=_summary(),
        validation_half_means_24bps=(0.0030, 0.0050),
        protected_oos_opened=False,
        genuine_forward_opened=False,
        broker_connected=False,
        trade_authority=False,
        promotion_authority=False,
    )


def _predeclaration() -> dict:
    return {
        "fingerprint_id": "DISC-SIGNED-VOLUME-DRIFT-001-v1",
        "contract_sha256": SHA_A,
    }


def _context() -> dict:
    return {
        "evidence_status": CERTIFIED_EVIDENCE_STATUS,
        "screen_id": "C101-SIGNED-VOLUME-STAGE1-v1",
        "screen_cutoff": "2026-08-31T23:00:00+00:00",
        "canonical_admission_receipt_sha256": SHA_B,
        "selection_dataset_receipt_sha256": SHA_C,
        "stage1_binding_receipt_sha256": SHA_D,
        "stage1_execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "chronology_pass": True,
        "point_in_time_pass": True,
        "data_contract_pass": True,
        "liquidity_capacity_pass": True,
    }


def test_certified_result_maps_exactly_to_failure_learning_screen() -> None:
    screen = build_failure_learning_screen(_result(), _predeclaration(), _context())

    assert screen["schema_version"] == 1
    assert screen["fingerprint_id"] == "DISC-SIGNED-VOLUME-DRIFT-001-v1"
    assert screen["contract_sha256"] == SHA_A
    assert screen["validation"] == {
        "trades": 23,
        "gross_mean_bps": pytest.approx(64.0),
        "net_mean_bps": pytest.approx(40.0),
        "profit_factor": pytest.approx(1.40),
        "half_net_bps": [pytest.approx(30.0), pytest.approx(50.0)],
    }
    assert screen["cost_stress"] == [
        {"multiplier": 1.0, "net_mean_bps": pytest.approx(40.0)},
        {"multiplier": 2.0, "net_mean_bps": pytest.approx(16.0)},
        {"multiplier": 3.0, "net_mean_bps": pytest.approx(-8.0)},
    ]
    assert screen["risk"] == {
        "worst_event_net_bps": pytest.approx(-60.0),
        "winner_concentration_share": pytest.approx(0.30),
        "without_best_net_mean_bps": pytest.approx(15.0),
    }
    assert screen["capacity"] == {"liquidity_capacity_pass": True}
    assert screen["asset_timeframe_cells"] == []
    assert screen["regime_cells"] == []
    assert screen["untouched_oos_opened"] is False
    assert screen["genuine_forward_opened"] is False
    assert screen["certified_evidence_receipts"] == {
        "canonical_admission_receipt_sha256": SHA_B,
        "selection_dataset_receipt_sha256": SHA_C,
        "stage1_binding_receipt_sha256": SHA_D,
        "stage1_execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
    }


def test_test_only_or_caller_result_cannot_mint_canonical_screen() -> None:
    with pytest.raises(RuntimeError, match="TEST_ONLY/caller-supplied"):
        build_failure_learning_screen(
            _result(evidence_status="TEST_ONLY_UNTRUSTED"),
            _predeclaration(),
            _context(),
        )


def test_missing_authority_field_fails_closed() -> None:
    result = _result()
    delattr(result, "evidence_status")
    with pytest.raises(RuntimeError, match="missing required field: evidence_status"):
        build_failure_learning_screen(result, _predeclaration(), _context())


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("stage1_execution_contract_sha256", SHA_B, "wrong Stage-1 execution contract"),
        ("chronology_pass", False, "chronology_pass must be true"),
        ("point_in_time_pass", False, "point_in_time_pass must be true"),
        ("data_contract_pass", False, "data_contract_pass must be true"),
        ("liquidity_capacity_pass", False, "liquidity_capacity_pass must be true"),
    ],
)
def test_certified_context_must_preserve_exact_scientific_authority(
    field: str,
    value: object,
    match: str,
) -> None:
    context = _context()
    context[field] = value
    with pytest.raises(RuntimeError, match=match):
        build_failure_learning_screen(_result(), _predeclaration(), context)


def test_candidate_and_safety_mismatches_fail_closed() -> None:
    wrong_candidate = _result()
    wrong_candidate.candidate_id = "DISC-RESIDUAL-REV-001-v1"
    with pytest.raises(RuntimeError, match="candidate_id does not match"):
        build_failure_learning_screen(wrong_candidate, _predeclaration(), _context())

    unsafe = _result()
    unsafe.trade_authority = True
    with pytest.raises(RuntimeError, match="trade_authority=False"):
        build_failure_learning_screen(unsafe, _predeclaration(), _context())

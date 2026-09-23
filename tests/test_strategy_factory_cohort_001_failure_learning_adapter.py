from __future__ import annotations

from types import SimpleNamespace

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_failure_diagnostics import (
    Stage1FailureDiagnostics,
)
from orchestration.cohorts.strategy_factory_cohort_001_failure_learning_adapter import (
    CANONICAL_ADMISSION_RECEIPT_SHA256,
    CERTIFIED_EVIDENCE_STATUS,
    EXECUTION_CONTRACT_SHA256,
    SCREEN_CUTOFF,
    SELECTION_DATASET_RECEIPT_SHA256,
    STAGE1_BINDING_RECEIPT_SHA256,
    _map_certified_failure_learning_screen,
    build_failure_learning_screen,
)


PREDECLARATION_SHA = "a" * 64


def _summary() -> SimpleNamespace:
    return SimpleNamespace(
        independent_events=23,
        mean_24bps=0.0040,
        mean_72bps=-0.0008,
        profit_factor_24bps=1.40,
        leave_best_mean_24bps=0.0015,
        worst_loss_abs_24bps=0.0060,
    )


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id="DISC-SIGNED-VOLUME-DRIFT-001-v1",
        validation=_summary(),
        validation_half_means_24bps=(0.0030, 0.0050),
        protected_oos_opened=False,
        genuine_forward_opened=False,
        broker_connected=False,
        trade_authority=False,
        promotion_authority=False,
    )


def _diagnostics() -> Stage1FailureDiagnostics:
    return Stage1FailureDiagnostics(
        candidate_id="DISC-SIGNED-VOLUME-DRIFT-001-v1",
        validation_independent_events=23,
        mean_48bps=0.0016,
        winner_concentration_share_24bps=0.30,
        mean_0bps=0.0051,
    )


def _predeclaration() -> dict:
    return {
        "fingerprint_id": "DISC-SIGNED-VOLUME-DRIFT-001-v1",
        "contract_sha256": PREDECLARATION_SHA,
    }


def _context() -> dict:
    return {
        "evidence_status": CERTIFIED_EVIDENCE_STATUS,
        "screen_id": "C101-SIGNED-VOLUME-STAGE1-v1",
        "screen_cutoff": SCREEN_CUTOFF,
        "canonical_admission_receipt_sha256": CANONICAL_ADMISSION_RECEIPT_SHA256,
        "selection_dataset_receipt_sha256": SELECTION_DATASET_RECEIPT_SHA256,
        "stage1_binding_receipt_sha256": STAGE1_BINDING_RECEIPT_SHA256,
        "stage1_execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "chronology_pass": True,
        "point_in_time_pass": True,
        "data_contract_pass": True,
        "liquidity_capacity_pass": True,
    }


def test_private_mapper_preserves_exact_failure_learning_semantics() -> None:
    screen = _map_certified_failure_learning_screen(
        _result(),
        _diagnostics(),
        _predeclaration(),
        _context(),
    )

    assert screen["schema_version"] == 1
    assert screen["fingerprint_id"] == "DISC-SIGNED-VOLUME-DRIFT-001-v1"
    assert screen["contract_sha256"] == PREDECLARATION_SHA
    assert screen["validation"]["trades"] == 23
    # Gross comes from the zero-cost clustered portfolio diagnostic, not from
    # adding a flat 24 bps to the independent-event net mean.
    assert screen["validation"]["gross_mean_bps"] == pytest.approx(51.0)
    assert screen["validation"]["gross_mean_bps"] != pytest.approx(64.0)
    assert screen["validation"]["net_mean_bps"] == pytest.approx(40.0)
    assert screen["validation"]["profit_factor"] == pytest.approx(1.40)
    assert screen["validation"]["half_net_bps"] == pytest.approx([30.0, 50.0])
    assert [row["multiplier"] for row in screen["cost_stress"]] == [1.0, 2.0, 3.0]
    assert [row["net_mean_bps"] for row in screen["cost_stress"]] == pytest.approx([40.0, 16.0, -8.0])
    assert screen["risk"]["worst_event_net_bps"] == pytest.approx(-60.0)
    assert screen["risk"]["winner_concentration_share"] == pytest.approx(0.30)
    assert screen["risk"]["without_best_net_mean_bps"] == pytest.approx(15.0)
    assert screen["capacity"] == {"liquidity_capacity_pass": True}
    assert screen["asset_timeframe_cells"] == []
    assert screen["regime_cells"] == []
    assert screen["untouched_oos_opened"] is False
    assert screen["genuine_forward_opened"] is False
    assert screen["certified_evidence_receipts"] == {
        "canonical_admission_receipt_sha256": CANONICAL_ADMISSION_RECEIPT_SHA256,
        "selection_dataset_receipt_sha256": SELECTION_DATASET_RECEIPT_SHA256,
        "stage1_binding_receipt_sha256": STAGE1_BINDING_RECEIPT_SHA256,
        "stage1_execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
    }


def test_private_mapper_requires_direct_gross_diagnostic_when_events_exist() -> None:
    diagnostics = Stage1FailureDiagnostics(
        candidate_id="DISC-SIGNED-VOLUME-DRIFT-001-v1",
        validation_independent_events=23,
        mean_48bps=0.0016,
        winner_concentration_share_24bps=0.30,
        mean_0bps=None,
    )
    with pytest.raises(RuntimeError, match="mean_0bps must be defined"):
        _map_certified_failure_learning_screen(
            _result(), diagnostics, _predeclaration(), _context()
        )


def test_public_canonical_minting_remains_fail_closed_pre_integration() -> None:
    with pytest.raises(RuntimeError, match="canonical Cohort failure-learning minting is blocked"):
        build_failure_learning_screen(
            _result(),
            _diagnostics(),
            _predeclaration(),
            _context(),
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("stage1_execution_contract_sha256", "b" * 64, "does not match the frozen receipt"),
        ("selection_dataset_receipt_sha256", "c" * 64, "does not match the frozen receipt"),
        ("screen_cutoff", "2026-09-01T00:00:00+00:00", "development cutoff"),
        ("chronology_pass", False, "chronology_pass must be true"),
        ("point_in_time_pass", False, "point_in_time_pass must be true"),
        ("data_contract_pass", False, "data_contract_pass must be true"),
        ("liquidity_capacity_pass", False, "liquidity_capacity_pass must be true"),
    ],
)
def test_private_mapper_requires_exact_certified_context(
    field: str,
    value: object,
    match: str,
) -> None:
    context = _context()
    context[field] = value
    with pytest.raises(RuntimeError, match=match):
        _map_certified_failure_learning_screen(
            _result(),
            _diagnostics(),
            _predeclaration(),
            context,
        )


def test_candidate_diagnostic_and_safety_mismatches_fail_closed() -> None:
    wrong_candidate = _result()
    wrong_candidate.candidate_id = "DISC-RESIDUAL-REV-001-v1"
    with pytest.raises(RuntimeError, match="candidate_id does not match"):
        _map_certified_failure_learning_screen(
            wrong_candidate,
            _diagnostics(),
            _predeclaration(),
            _context(),
        )

    wrong_diagnostics = Stage1FailureDiagnostics(
        candidate_id="DISC-RESIDUAL-REV-001-v1",
        validation_independent_events=23,
        mean_48bps=0.0016,
        winner_concentration_share_24bps=0.30,
        mean_0bps=0.0051,
    )
    with pytest.raises(RuntimeError, match="diagnostics candidate_id"):
        _map_certified_failure_learning_screen(
            _result(),
            wrong_diagnostics,
            _predeclaration(),
            _context(),
        )

    unsafe = _result()
    unsafe.trade_authority = True
    with pytest.raises(RuntimeError, match="trade_authority=False"):
        _map_certified_failure_learning_screen(
            unsafe,
            _diagnostics(),
            _predeclaration(),
            _context(),
        )

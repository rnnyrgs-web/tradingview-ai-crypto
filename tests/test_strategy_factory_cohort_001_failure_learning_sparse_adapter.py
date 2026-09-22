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
)


FINGERPRINT = "DISC-WEEKEND-NORMALIZE-001-v1"
CONTRACT_SHA = "a" * 64


def _result(validation: SimpleNamespace, halves: tuple[float | None, float | None]) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id=FINGERPRINT,
        validation=validation,
        validation_half_means_24bps=halves,
        protected_oos_opened=False,
        genuine_forward_opened=False,
        broker_connected=False,
        trade_authority=False,
        promotion_authority=False,
    )


def _context() -> dict:
    return {
        "evidence_status": CERTIFIED_EVIDENCE_STATUS,
        "screen_id": "C101-WEEKEND-STAGE1-v1",
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


def _predeclaration() -> dict:
    return {"fingerprint_id": FINGERPRINT, "contract_sha256": CONTRACT_SHA}


def test_zero_event_sparse_screen_preserves_undefined_statistics_as_null() -> None:
    validation = SimpleNamespace(
        independent_events=0,
        mean_24bps=None,
        mean_72bps=None,
        profit_factor_24bps=None,
        leave_best_mean_24bps=None,
        worst_loss_abs_24bps=None,
    )
    diagnostics = Stage1FailureDiagnostics(
        candidate_id=FINGERPRINT,
        validation_independent_events=0,
        mean_48bps=None,
        winner_concentration_share_24bps=None,
    )

    screen = _map_certified_failure_learning_screen(
        _result(validation, (None, None)), diagnostics, _predeclaration(), _context()
    )

    assert screen["validation"] == {
        "trades": 0,
        "gross_mean_bps": None,
        "net_mean_bps": None,
        "profit_factor": None,
        "half_net_bps": [None, None],
    }
    assert [row["net_mean_bps"] for row in screen["cost_stress"]] == [None, None, None]
    assert screen["risk"] == {
        "worst_event_net_bps": None,
        "winner_concentration_share": None,
        "without_best_net_mean_bps": None,
    }


def test_no_loss_profit_factor_and_one_sparse_half_are_not_fabricated() -> None:
    validation = SimpleNamespace(
        independent_events=1,
        mean_24bps=0.012,
        mean_72bps=0.0072,
        profit_factor_24bps=float("inf"),
        leave_best_mean_24bps=None,
        worst_loss_abs_24bps=0.0,
    )
    diagnostics = Stage1FailureDiagnostics(
        candidate_id=FINGERPRINT,
        validation_independent_events=1,
        mean_48bps=0.0096,
        winner_concentration_share_24bps=1.0,
    )

    screen = _map_certified_failure_learning_screen(
        _result(validation, (0.012, None)), diagnostics, _predeclaration(), _context()
    )

    assert screen["validation"]["profit_factor"] == float("inf")
    assert screen["validation"]["half_net_bps"] == [pytest.approx(120.0), None]
    assert screen["risk"]["without_best_net_mean_bps"] is None
    assert screen["risk"]["winner_concentration_share"] == 1.0


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("mean_24bps", float("inf"), "finite when defined"),
        ("mean_72bps", float("nan"), "must not be NaN"),
        ("profit_factor_24bps", float("-inf"), "negative infinity"),
    ],
)
def test_invalid_nonfinite_sparse_values_still_fail_closed(field: str, value: float, match: str) -> None:
    values = {
        "independent_events": 1,
        "mean_24bps": 0.01,
        "mean_72bps": 0.005,
        "profit_factor_24bps": 1.2,
        "leave_best_mean_24bps": None,
        "worst_loss_abs_24bps": 0.0,
    }
    values[field] = value
    validation = SimpleNamespace(**values)
    diagnostics = Stage1FailureDiagnostics(
        candidate_id=FINGERPRINT,
        validation_independent_events=1,
        mean_48bps=0.0075,
        winner_concentration_share_24bps=1.0,
    )

    with pytest.raises(RuntimeError, match=match):
        _map_certified_failure_learning_screen(
            _result(validation, (0.01, None)), diagnostics, _predeclaration(), _context()
        )

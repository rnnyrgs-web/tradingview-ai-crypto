from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchestration.cohorts.strategy_factory_cohort_001_failure_diagnostics import (
    Stage1FailureDiagnostics,
)


CERTIFIED_EVIDENCE_STATUS = "CERTIFIED_COHORT_DEVELOPMENT_ONLY"
CANONICAL_ADMISSION_RECEIPT_SHA256 = "fc7c237e67600390cca369965161ccfc555dd2bc9bebbabc83d774fafd57182a"
SELECTION_DATASET_RECEIPT_SHA256 = "910759b7448baec737f5a884b9531cf29726a842e09aa54abbd5cc6d9f4cab22"
STAGE1_BINDING_RECEIPT_SHA256 = "3a715c8373e3847dba2f0922bc99dbdd69b3864729be8c40d6d79db444fa43db"
EXECUTION_CONTRACT_SHA256 = "04b4fd2373649061ca8349e7dbff127cc7b0bc852a9f4ff541b080094da187ef"
SCREEN_CUTOFF = "2026-08-31T23:00:00+00:00"

_REQUIRED_BINDINGS = {
    "canonical_admission_receipt_sha256": CANONICAL_ADMISSION_RECEIPT_SHA256,
    "selection_dataset_receipt_sha256": SELECTION_DATASET_RECEIPT_SHA256,
    "stage1_binding_receipt_sha256": STAGE1_BINDING_RECEIPT_SHA256,
    "stage1_execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
}


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise RuntimeError(f"{field} must be finite")
    return number


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field} must be non-empty text")
    return value.strip()


def _sha256_text(value: Any, field: str) -> str:
    text = _nonempty_text(value, field)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise RuntimeError(f"{field} must be a lowercase SHA-256 hex digest")
    return text


def _attribute(obj: Any, name: str) -> Any:
    if not hasattr(obj, name):
        raise RuntimeError(f"Stage-1 result is missing required field: {name}")
    return getattr(obj, name)


def _require_false(obj: Any, name: str) -> None:
    if _attribute(obj, name) is not False:
        raise RuntimeError(f"Stage-1 result must keep {name}=False")


def _validate_certified_context(certified_context: Mapping[str, Any]) -> None:
    if certified_context.get("evidence_status") != CERTIFIED_EVIDENCE_STATUS:
        raise RuntimeError("certified context does not authorize canonical Cohort evidence")
    for field, expected in _REQUIRED_BINDINGS.items():
        observed = _sha256_text(certified_context.get(field), f"certified_context.{field}")
        if observed != expected:
            raise RuntimeError(f"certified_context.{field} does not match the frozen receipt")
    if certified_context.get("screen_cutoff") != SCREEN_CUTOFF:
        raise RuntimeError("certified_context.screen_cutoff does not match the frozen development cutoff")
    for field in (
        "chronology_pass",
        "point_in_time_pass",
        "data_contract_pass",
        "liquidity_capacity_pass",
    ):
        if certified_context.get(field) is not True:
            raise RuntimeError(f"certified_context.{field} must be true")


def _map_certified_failure_learning_screen(
    result: Any,
    diagnostics: Stage1FailureDiagnostics,
    predeclaration: Mapping[str, Any],
    certified_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Private schema mapper for a future separately reviewed certified adapter.

    This function does not establish dataset authority. The public canonical mint
    remains disabled until a dedicated adapter authenticates exact protected-safe
    dataset bytes/receipt, chronology/PIT and a pre-frozen capacity rule.
    """
    fingerprint_id = _nonempty_text(
        predeclaration.get("fingerprint_id"),
        "predeclaration.fingerprint_id",
    )
    contract_sha256 = _sha256_text(
        predeclaration.get("contract_sha256"),
        "predeclaration.contract_sha256",
    )
    if _attribute(result, "candidate_id") != fingerprint_id:
        raise RuntimeError("Stage-1 result candidate_id does not match predeclaration fingerprint_id")
    if diagnostics.candidate_id != fingerprint_id:
        raise RuntimeError("failure diagnostics candidate_id does not match predeclaration fingerprint_id")

    for name in (
        "protected_oos_opened",
        "genuine_forward_opened",
        "broker_connected",
        "trade_authority",
        "promotion_authority",
    ):
        _require_false(result, name)
    _validate_certified_context(certified_context)

    validation = _attribute(result, "validation")
    independent_events = _attribute(validation, "independent_events")
    if isinstance(independent_events, bool) or not isinstance(independent_events, int) or independent_events < 0:
        raise RuntimeError("validation.independent_events must be a non-negative integer")
    if diagnostics.validation_independent_events != independent_events:
        raise RuntimeError("failure diagnostics independent-event count does not match Stage-1 result")

    mean_24 = _finite_number(_attribute(validation, "mean_24bps"), "validation.mean_24bps")
    mean_48 = _finite_number(diagnostics.mean_48bps, "failure_diagnostics.mean_48bps")
    mean_72 = _finite_number(_attribute(validation, "mean_72bps"), "validation.mean_72bps")
    profit_factor = _finite_number(
        _attribute(validation, "profit_factor_24bps"),
        "validation.profit_factor_24bps",
    )
    leave_best = _finite_number(
        _attribute(validation, "leave_best_mean_24bps"),
        "validation.leave_best_mean_24bps",
    )
    worst_loss_abs = _finite_number(
        _attribute(validation, "worst_loss_abs_24bps"),
        "validation.worst_loss_abs_24bps",
    )
    winner_share = _finite_number(
        diagnostics.winner_concentration_share_24bps,
        "failure_diagnostics.winner_concentration_share_24bps",
    )
    if worst_loss_abs < 0:
        raise RuntimeError("validation.worst_loss_abs_24bps must be non-negative")
    if not 0.0 <= winner_share <= 1.0:
        raise RuntimeError("failure_diagnostics.winner_concentration_share_24bps must be in [0,1]")

    half_means = _attribute(result, "validation_half_means_24bps")
    if not isinstance(half_means, tuple) or len(half_means) != 2:
        raise RuntimeError("validation_half_means_24bps must contain exactly two frozen halves")
    half_bps = [
        _finite_number(value, f"validation_half_means_24bps[{idx}]") * 10_000.0
        for idx, value in enumerate(half_means)
    ]

    screen_id = _nonempty_text(certified_context.get("screen_id"), "certified_context.screen_id")
    return {
        "schema_version": 1,
        "screen_id": screen_id,
        "fingerprint_id": fingerprint_id,
        "contract_sha256": contract_sha256,
        "screen_cutoff": SCREEN_CUTOFF,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "data_quality": {
            "chronology_pass": True,
            "point_in_time_pass": True,
            "data_contract_pass": True,
        },
        "validation": {
            "trades": independent_events,
            "gross_mean_bps": mean_24 * 10_000.0 + 24.0,
            "net_mean_bps": mean_24 * 10_000.0,
            "profit_factor": profit_factor,
            "half_net_bps": half_bps,
        },
        "cost_stress": [
            {"multiplier": 1.0, "net_mean_bps": mean_24 * 10_000.0},
            {"multiplier": 2.0, "net_mean_bps": mean_48 * 10_000.0},
            {"multiplier": 3.0, "net_mean_bps": mean_72 * 10_000.0},
        ],
        "risk": {
            "worst_event_net_bps": -worst_loss_abs * 10_000.0,
            "winner_concentration_share": winner_share,
            "without_best_net_mean_bps": leave_best * 10_000.0,
        },
        "asset_timeframe_cells": [],
        "regime_cells": [],
        "capacity": {"liquidity_capacity_pass": True},
        "certified_evidence_receipts": dict(_REQUIRED_BINDINGS),
    }


def build_failure_learning_screen(
    result: Any,
    diagnostics: Stage1FailureDiagnostics,
    predeclaration: Mapping[str, Any],
    certified_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Canonical minting intentionally remains unavailable pre-integration."""
    del result, diagnostics, predeclaration, certified_context
    raise RuntimeError(
        "canonical Cohort failure-learning minting is blocked until a separately reviewed "
        "certified dataset/capacity adapter authenticates the frozen evidence receipts"
    )

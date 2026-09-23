from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from orchestration.cohorts.strategy_factory_cohort_001_failure_diagnostics import (
    Stage1FailureDiagnostics,
)


CERTIFIED_EVIDENCE_STATUS = "CERTIFIED_COHORT_DEVELOPMENT_ONLY"
CANONICAL_ADMISSION_RECEIPT_SHA256 = "fc7c237e67600390cca369965161ccfc555dd2bc9bebbabc83d774fafd57182a"
SELECTION_DATASET_RECEIPT_SHA256 = "910759b7448baec737f5a884b9531cf29726a842e09aa54abbd5cc6d9f4cab22"
STAGE1_BINDING_RECEIPT_SHA256 = "53777547473c4d0857f6a1fd73949fe8371e8bfcc7b9893701ea7dbddc4ae7ab"
EXECUTION_CONTRACT_SHA256 = "58c7d6fa3db62c7589768b59af8e048acbf9ca1e904b0f7fd5df64f0c9bd19c5"
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
    if not math.isfinite(number):
        raise RuntimeError(f"{field} must be finite")
    return number


def _optional_number(
    value: Any,
    field: str,
    *,
    allow_positive_infinity: bool = False,
) -> float | None:
    """Preserve mathematically undefined sparse diagnostics without fabrication."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be numeric or null")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric or null") from exc
    if math.isnan(number) or number == float("-inf"):
        raise RuntimeError(f"{field} must not be NaN or negative infinity")
    if number == float("inf") and not allow_positive_infinity:
        raise RuntimeError(f"{field} must be finite when defined")
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

    Sparse Stage-1 statistics remain ``None`` when mathematically undefined.
    A no-loss profit factor may remain positive infinity, matching the truthful
    downstream #510/#511 schema. No zero/one/finite placeholder is fabricated.
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

    mean_24 = _optional_number(_attribute(validation, "mean_24bps"), "validation.mean_24bps")
    mean_48 = _optional_number(diagnostics.mean_48bps, "failure_diagnostics.mean_48bps")
    mean_72 = _optional_number(_attribute(validation, "mean_72bps"), "validation.mean_72bps")
    profit_factor = _optional_number(
        _attribute(validation, "profit_factor_24bps"),
        "validation.profit_factor_24bps",
        allow_positive_infinity=True,
    )
    leave_best = _optional_number(
        _attribute(validation, "leave_best_mean_24bps"),
        "validation.leave_best_mean_24bps",
    )
    worst_loss_abs = _optional_number(
        _attribute(validation, "worst_loss_abs_24bps"),
        "validation.worst_loss_abs_24bps",
    )
    winner_share = _optional_number(
        diagnostics.winner_concentration_share_24bps,
        "failure_diagnostics.winner_concentration_share_24bps",
    )
    if profit_factor is not None and profit_factor < 0:
        raise RuntimeError("validation.profit_factor_24bps must be non-negative when defined")
    if worst_loss_abs is not None and worst_loss_abs < 0:
        raise RuntimeError("validation.worst_loss_abs_24bps must be non-negative when defined")
    if winner_share is not None and not 0.0 <= winner_share <= 1.0:
        raise RuntimeError("failure_diagnostics.winner_concentration_share_24bps must be in [0,1]")

    half_means = _attribute(result, "validation_half_means_24bps")
    if not isinstance(half_means, tuple) or len(half_means) != 2:
        raise RuntimeError("validation_half_means_24bps must contain exactly two frozen halves")
    half_bps = [
        None if value is None else _finite_number(value, f"validation_half_means_24bps[{idx}]") * 10_000.0
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
            "gross_mean_bps": None if mean_24 is None else mean_24 * 10_000.0 + 24.0,
            "net_mean_bps": None if mean_24 is None else mean_24 * 10_000.0,
            "profit_factor": profit_factor,
            "half_net_bps": half_bps,
        },
        "cost_stress": [
            {"multiplier": 1.0, "net_mean_bps": None if mean_24 is None else mean_24 * 10_000.0},
            {"multiplier": 2.0, "net_mean_bps": None if mean_48 is None else mean_48 * 10_000.0},
            {"multiplier": 3.0, "net_mean_bps": None if mean_72 is None else mean_72 * 10_000.0},
        ],
        "risk": {
            "worst_event_net_bps": None if worst_loss_abs is None else -worst_loss_abs * 10_000.0,
            "winner_concentration_share": winner_share,
            "without_best_net_mean_bps": None if leave_best is None else leave_best * 10_000.0,
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

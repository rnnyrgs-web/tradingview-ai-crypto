from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from orchestration.rejected_fingerprints import (
    SEMANTIC_BACKFILL_UNAVAILABLE,
    is_rejected_fingerprint,
    load_rejected_fingerprints,
    rejection_record,
    semantic_rejection_record,
)
from orchestration.scientific_design_identity import (
    scientific_design_sha256,
    strategy_behavior_sha256,
)

SCHEMA_VERSION = 1

REQUIRED_FIELDS = {
    "schema_version",
    "hypothesis_id",
    "fingerprint_id",
    "family",
    "economic_mechanism",
    "hypothesis",
    "target_markets",
    "target_timeframes",
    "formation_cutoff",
    "data_contract",
    "signal_rules",
    "execution_rules",
    "cost_model",
    "search_plan",
    "validation_plan",
    "protected_evidence",
}

OUTCOME_DERIVED_FIELDS = {
    "pnl",
    "net_pnl",
    "return",
    "returns",
    "profit_factor",
    "sharpe",
    "sortino",
    "win_rate",
    "observed_score",
    "observed_performance",
    "backtest_result",
    "validation_result",
    "oos_result",
    "forward_result",
    "selected_threshold",
    "selected_parameter",
}

REQUIRED_COST_FIELDS = {
    "fees_bps",
    "spread_bps",
    "slippage_bps",
    "funding_bps_per_day",
    "stress_multipliers",
}

IDENTITY_FIELDS = {
    "contract_sha256",
    "scientific_design_sha256",
    "strategy_behavior_sha256",
}


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field} must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"{field} must be a non-empty list")
    result: list[str] = []
    for item in value:
        result.append(_require_text(item, field))
    if len(set(result)) != len(result):
        raise RuntimeError(f"{field} must not contain duplicates")
    return result


def _require_nonnegative_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric") from exc
    if number < 0:
        raise RuntimeError(f"{field} must be non-negative")
    return number


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RuntimeError(f"{field} must be a positive integer")
    return value


def _validate_formation_cutoff(value: Any) -> None:
    text = _require_text(value, "formation_cutoff")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError("formation_cutoff must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("formation_cutoff must include an explicit timezone")


def _find_outcome_fields(value: Any, path: str = "candidate") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}"
            if normalized in OUTCOME_DERIVED_FIELDS:
                found.append(child_path)
            found.extend(_find_outcome_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_outcome_fields(child, f"{path}[{index}]"))
    return found


def canonical_predeclaration_bytes(candidate: dict[str, Any]) -> bytes:
    """Return deterministic bytes for the full immutable pre-outcome contract.

    Identity digests are excluded from the contract digest because they are
    deterministic derivatives of the frozen fields. ``scientific_design_sha256``
    captures the full scientific protocol; ``strategy_behavior_sha256`` captures
    executable behavior for rejected-memory/no-rescue admission.
    """
    payload = {key: value for key, value in candidate.items() if key not in IDENTITY_FIELDS}
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("predeclaration must contain JSON-safe finite values") from exc
    return encoded.encode("utf-8")


def predeclaration_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_predeclaration_bytes(candidate)).hexdigest()


def _validate_predecessor_claims(
    candidate: dict[str, Any],
    active_rejections: list[dict[str, Any]],
) -> None:
    predecessors = candidate.get("predecessor_fingerprints")
    if predecessors is None:
        return
    predecessor_ids = _require_string_list(predecessors, "predecessor_fingerprints")
    for predecessor_id in predecessor_ids:
        record = rejection_record(predecessor_id, active_rejections)
        if (
            record is not None
            and record.get("do_not_resubmit_same_fingerprint")
            and record.get("semantic_identity_status") == SEMANTIC_BACKFILL_UNAVAILABLE
        ):
            raise RuntimeError(
                "predecessor has SEMANTIC_BACKFILL_UNAVAILABLE; material distinctness "
                f"cannot be auto-certified: {predecessor_id}"
            )


def validate_predeclaration(
    candidate: dict[str, Any],
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> str:
    """Validate an outcome-blind strategy cheap-screen predeclaration.

    This is a research admission contract only. Passing it grants no OOS,
    forward, promotion, broker or trade authority.
    """
    if not isinstance(candidate, dict):
        raise RuntimeError("predeclaration must be an object")

    missing = sorted(REQUIRED_FIELDS - set(candidate))
    if missing:
        raise RuntimeError(f"predeclaration missing fields: {missing}")
    if candidate.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"schema_version must equal {SCHEMA_VERSION}")

    hypothesis_id = _require_text(candidate["hypothesis_id"], "hypothesis_id")
    fingerprint_id = _require_text(candidate["fingerprint_id"], "fingerprint_id")
    _require_text(candidate["family"], "family")
    _require_text(candidate["economic_mechanism"], "economic_mechanism")
    _require_text(candidate["hypothesis"], "hypothesis")
    _require_string_list(candidate["target_markets"], "target_markets")
    _require_string_list(candidate["target_timeframes"], "target_timeframes")
    _validate_formation_cutoff(candidate["formation_cutoff"])

    for field in ("data_contract", "signal_rules", "execution_rules"):
        value = candidate[field]
        if not isinstance(value, dict) or not value:
            raise RuntimeError(f"{field} must be a non-empty object")

    outcome_fields = _find_outcome_fields(candidate)
    if outcome_fields:
        raise RuntimeError(
            "predeclaration contains outcome-derived fields: " + ", ".join(sorted(outcome_fields))
        )

    costs = candidate["cost_model"]
    if not isinstance(costs, dict):
        raise RuntimeError("cost_model must be an object")
    missing_costs = sorted(REQUIRED_COST_FIELDS - set(costs))
    if missing_costs:
        raise RuntimeError(f"cost_model missing fields: {missing_costs}")
    for field in ("fees_bps", "spread_bps", "slippage_bps", "funding_bps_per_day"):
        _require_nonnegative_number(costs[field], f"cost_model.{field}")
    multipliers = costs["stress_multipliers"]
    if not isinstance(multipliers, list) or not multipliers:
        raise RuntimeError("cost_model.stress_multipliers must be a non-empty list")
    normalized_multipliers = [
        _require_nonnegative_number(value, "cost_model.stress_multipliers") for value in multipliers
    ]
    if any(value < 1.0 for value in normalized_multipliers):
        raise RuntimeError("cost_model.stress_multipliers cannot reduce frozen base costs")
    if 1.0 not in normalized_multipliers:
        raise RuntimeError("cost_model.stress_multipliers must include the 1x base-cost case")
    if normalized_multipliers != sorted(set(normalized_multipliers)):
        raise RuntimeError("cost_model.stress_multipliers must be sorted and unique")

    search = candidate["search_plan"]
    if not isinstance(search, dict):
        raise RuntimeError("search_plan must be an object")
    _require_text(search.get("multiple_testing_family_id"), "search_plan.multiple_testing_family_id")
    _require_positive_int(search.get("planned_hypothesis_count"), "search_plan.planned_hypothesis_count")
    _require_positive_int(search.get("planned_parameter_variants"), "search_plan.planned_parameter_variants")

    validation = candidate["validation_plan"]
    if not isinstance(validation, dict):
        raise RuntimeError("validation_plan must be an object")
    required_true = (
        "chronological",
        "selection_uses_training_and_validation_only",
        "untouched_oos_required",
        "genuine_forward_required",
    )
    for field in required_true:
        if validation.get(field) is not True:
            raise RuntimeError(f"validation_plan.{field} must be true")

    protected = candidate["protected_evidence"]
    if not isinstance(protected, dict):
        raise RuntimeError("protected_evidence must be an object")
    if protected.get("untouched_oos_opened") is not False:
        raise RuntimeError("untouched OOS must remain locked at predeclaration")
    if protected.get("genuine_forward_opened") is not False:
        raise RuntimeError("genuine-forward evidence must remain locked at predeclaration")

    active_rejections = (
        rejected_entries if rejected_entries is not None else load_rejected_fingerprints()
    )
    if is_rejected_fingerprint(fingerprint_id, active_rejections):
        raise RuntimeError(f"rejected fingerprint cannot be predeclared again: {fingerprint_id}")

    design_digest = scientific_design_sha256(candidate)
    behavior_digest = strategy_behavior_sha256(candidate)
    semantic_rejection = semantic_rejection_record(
        behavior_digest,
        active_rejections,
        scientific_design_digest=design_digest,
    )
    if semantic_rejection is not None:
        raise RuntimeError(
            "rejected strategy behavior cannot be predeclared under a renamed/cosmetic or "
            "validation-only identity: "
            f"{semantic_rejection['fingerprint_id']}"
        )
    _validate_predecessor_claims(candidate, active_rejections)

    supplied_design_digest = candidate.get("scientific_design_sha256")
    if supplied_design_digest is not None:
        if not isinstance(supplied_design_digest, str) or supplied_design_digest != design_digest:
            raise RuntimeError(
                "scientific_design_sha256 does not match the computed full scientific protocol"
            )

    supplied_behavior_digest = candidate.get("strategy_behavior_sha256")
    if supplied_behavior_digest is not None:
        if (
            not isinstance(supplied_behavior_digest, str)
            or supplied_behavior_digest != behavior_digest
        ):
            raise RuntimeError(
                "strategy_behavior_sha256 does not match the computed executable behavior"
            )

    digest = predeclaration_sha256(candidate)
    supplied_digest = candidate.get("contract_sha256")
    if supplied_digest is not None:
        if supplied_design_digest is None or supplied_behavior_digest is None:
            raise RuntimeError(
                "frozen predeclaration with contract_sha256 must persist both "
                "scientific_design_sha256 and strategy_behavior_sha256"
            )
        if not isinstance(supplied_digest, str) or supplied_digest != digest:
            raise RuntimeError("contract_sha256 does not match the frozen predeclaration")

    if hypothesis_id == fingerprint_id:
        raise RuntimeError(
            "fingerprint_id must version the hypothesis rather than duplicate hypothesis_id"
        )
    return digest


def freeze_predeclaration(
    candidate: dict[str, Any],
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate and return a detached contract carrying immutable identities."""
    detached = json.loads(json.dumps(candidate, allow_nan=False))
    detached.pop("contract_sha256", None)
    detached.pop("scientific_design_sha256", None)
    detached.pop("strategy_behavior_sha256", None)

    validate_predeclaration(detached, rejected_entries=rejected_entries)
    detached["scientific_design_sha256"] = scientific_design_sha256(detached)
    detached["strategy_behavior_sha256"] = strategy_behavior_sha256(detached)
    detached["contract_sha256"] = predeclaration_sha256(detached)
    validate_predeclaration(detached, rejected_entries=rejected_entries)
    return detached

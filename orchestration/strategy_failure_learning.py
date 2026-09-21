from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from orchestration.rejected_fingerprints import is_rejected_fingerprint
from orchestration.strategy_predeclaration import freeze_predeclaration, validate_predeclaration

SCHEMA_VERSION = 1

FAILURE_NO_GROSS_EDGE = "NO_GROSS_EDGE"
FAILURE_COST_ERASED_EDGE = "COST_ERASED_EDGE"
FAILURE_UNDERPOWERED = "UNDERPOWERED_INCONCLUSIVE"
FAILURE_REGIME_INSTABILITY = "REGIME_INSTABILITY"
FAILURE_ASSET_TIMEFRAME = "ASSET_TIMEFRAME_DEPENDENCE"
FAILURE_TAIL = "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION"
FAILURE_DATA = "DATA_PIT_OR_CHRONOLOGY_WEAKNESS"
FAILURE_CAPACITY = "CAPACITY_OR_LIQUIDITY_WEAKNESS"
FAILURE_DUPLICATE = "DUPLICATE_OR_REJECTED_MECHANISM"

REJECTING_FAILURES = {
    FAILURE_NO_GROSS_EDGE,
    FAILURE_COST_ERASED_EDGE,
    FAILURE_REGIME_INSTABILITY,
    FAILURE_ASSET_TIMEFRAME,
    FAILURE_TAIL,
    FAILURE_CAPACITY,
    FAILURE_DUPLICATE,
}
INCONCLUSIVE_FAILURES = {FAILURE_UNDERPOWERED, FAILURE_DATA}

ALLOWED_CHANGE_DIMENSIONS = {
    "economic_mechanism",
    "structural_component",
    "data_source",
    "execution_premise",
    "market_structure",
    "regime_conditioning",
}


def _num(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise RuntimeError(f"{field} must be finite")
    return number


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RuntimeError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{field} must be a non-negative integer")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field} must be non-empty text")
    return value.strip()


def _time(value: Any, field: str) -> datetime:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(f"{field} must include a timezone")
    return parsed


def _failure_plan(predeclaration: dict[str, Any]) -> dict[str, Any]:
    plan = predeclaration.get("failure_learning_plan")
    if not isinstance(plan, dict):
        raise RuntimeError("predeclaration.failure_learning_plan is required for automatic failure learning")
    required = {
        "minimum_validation_trades",
        "minimum_cell_trades",
        "minimum_stable_cell_fraction",
        "catastrophic_event_loss_bps",
        "max_winner_concentration_share",
        "require_positive_validation_halves",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise RuntimeError(f"failure_learning_plan missing fields: {missing}")
    _positive_int(plan["minimum_validation_trades"], "failure_learning_plan.minimum_validation_trades")
    _positive_int(plan["minimum_cell_trades"], "failure_learning_plan.minimum_cell_trades")
    stable_fraction = _num(plan["minimum_stable_cell_fraction"], "failure_learning_plan.minimum_stable_cell_fraction")
    winner_share = _num(plan["max_winner_concentration_share"], "failure_learning_plan.max_winner_concentration_share")
    tail = _num(plan["catastrophic_event_loss_bps"], "failure_learning_plan.catastrophic_event_loss_bps")
    if not 0 < stable_fraction <= 1:
        raise RuntimeError("failure_learning_plan.minimum_stable_cell_fraction must be in (0, 1]")
    if not 0 < winner_share <= 1:
        raise RuntimeError("failure_learning_plan.max_winner_concentration_share must be in (0, 1]")
    if tail <= 0:
        raise RuntimeError("failure_learning_plan.catastrophic_event_loss_bps must be positive")
    if not isinstance(plan["require_positive_validation_halves"], bool):
        raise RuntimeError("failure_learning_plan.require_positive_validation_halves must be boolean")
    return plan


def _validate_screen_identity(predeclaration: dict[str, Any], screen: dict[str, Any]) -> None:
    if not isinstance(screen, dict):
        raise RuntimeError("screen result must be an object")
    if screen.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"screen.schema_version must equal {SCHEMA_VERSION}")
    if screen.get("fingerprint_id") != predeclaration.get("fingerprint_id"):
        raise RuntimeError("screen fingerprint does not match frozen predeclaration")
    if screen.get("contract_sha256") != predeclaration.get("contract_sha256"):
        raise RuntimeError("screen contract_sha256 does not match frozen predeclaration")
    _text(screen.get("screen_id"), "screen.screen_id")
    _time(screen.get("screen_cutoff"), "screen.screen_cutoff")
    if screen.get("untouched_oos_opened") is not False:
        raise RuntimeError("screen must not open untouched OOS")
    if screen.get("genuine_forward_opened") is not False:
        raise RuntimeError("screen must not open genuine-forward evidence")


def _cell_failures(screen: dict[str, Any], plan: dict[str, Any]) -> set[str]:
    failures: set[str] = set()
    min_trades = int(plan["minimum_cell_trades"])
    threshold = float(plan["minimum_stable_cell_fraction"])

    cells = screen.get("asset_timeframe_cells", [])
    if cells:
        if not isinstance(cells, list):
            raise RuntimeError("screen.asset_timeframe_cells must be a list")
        eligible = []
        for idx, cell in enumerate(cells):
            if not isinstance(cell, dict):
                raise RuntimeError(f"screen.asset_timeframe_cells[{idx}] must be an object")
            trades = _nonnegative_int(cell.get("trades"), f"screen.asset_timeframe_cells[{idx}].trades")
            net = _num(cell.get("net_mean_bps"), f"screen.asset_timeframe_cells[{idx}].net_mean_bps")
            if trades >= min_trades:
                eligible.append(net)
        if len(eligible) >= 2:
            positive_fraction = sum(value > 0 for value in eligible) / len(eligible)
            if positive_fraction < threshold:
                failures.add(FAILURE_ASSET_TIMEFRAME)

    regimes = screen.get("regime_cells", [])
    if regimes:
        if not isinstance(regimes, list):
            raise RuntimeError("screen.regime_cells must be a list")
        eligible_regimes = []
        for idx, cell in enumerate(regimes):
            if not isinstance(cell, dict):
                raise RuntimeError(f"screen.regime_cells[{idx}] must be an object")
            trades = _nonnegative_int(cell.get("trades"), f"screen.regime_cells[{idx}].trades")
            net = _num(cell.get("net_mean_bps"), f"screen.regime_cells[{idx}].net_mean_bps")
            if trades >= min_trades:
                eligible_regimes.append(net)
        if len(eligible_regimes) >= 2 and any(v > 0 for v in eligible_regimes) and any(v <= 0 for v in eligible_regimes):
            failures.add(FAILURE_REGIME_INSTABILITY)
    return failures


def classify_failure(
    predeclaration: dict[str, Any],
    screen: dict[str, Any],
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify a cheap-screen outcome without opening protected evidence.

    The classifier only uses thresholds that were embedded in the hashed
    predeclaration before this screen was evaluated.
    """
    validate_predeclaration(predeclaration, rejected_entries=rejected_entries)
    _validate_screen_identity(predeclaration, screen)
    plan = _failure_plan(predeclaration)

    duplicate_id = screen.get("duplicate_of_rejected_fingerprint")
    if duplicate_id is not None:
        duplicate_id = _text(duplicate_id, "screen.duplicate_of_rejected_fingerprint")
        if not is_rejected_fingerprint(duplicate_id, rejected_entries):
            raise RuntimeError("duplicate_of_rejected_fingerprint is not present in durable rejected memory")
        return {
            "status": "REJECTED",
            "failure_categories": [FAILURE_DUPLICATE],
            "rejection_eligible": True,
            "protected_evidence_opened": False,
        }

    quality = screen.get("data_quality")
    if not isinstance(quality, dict):
        raise RuntimeError("screen.data_quality must be an object")
    required_quality = ("chronology_pass", "point_in_time_pass", "data_contract_pass")
    if any(quality.get(key) is not True for key in required_quality):
        return {
            "status": "INCONCLUSIVE",
            "failure_categories": [FAILURE_DATA],
            "rejection_eligible": False,
            "protected_evidence_opened": False,
        }

    validation = screen.get("validation")
    if not isinstance(validation, dict):
        raise RuntimeError("screen.validation must be an object")
    trades = _nonnegative_int(validation.get("trades"), "screen.validation.trades")
    gross = _num(validation.get("gross_mean_bps"), "screen.validation.gross_mean_bps")
    net = _num(validation.get("net_mean_bps"), "screen.validation.net_mean_bps")
    _num(validation.get("profit_factor"), "screen.validation.profit_factor")
    halves = validation.get("half_net_bps")
    if not isinstance(halves, list) or len(halves) != 2:
        raise RuntimeError("screen.validation.half_net_bps must contain exactly two chronological halves")
    half_values = [_num(v, "screen.validation.half_net_bps") for v in halves]

    risk = screen.get("risk")
    if not isinstance(risk, dict):
        raise RuntimeError("screen.risk must be an object")
    worst_event = _num(risk.get("worst_event_net_bps"), "screen.risk.worst_event_net_bps")
    winner_share = _num(risk.get("winner_concentration_share"), "screen.risk.winner_concentration_share")
    without_best = _num(risk.get("without_best_net_mean_bps"), "screen.risk.without_best_net_mean_bps")
    if not 0 <= winner_share <= 1:
        raise RuntimeError("screen.risk.winner_concentration_share must be in [0, 1]")

    failures: set[str] = set()
    if worst_event <= -float(plan["catastrophic_event_loss_bps"]):
        failures.add(FAILURE_TAIL)
    if winner_share >= float(plan["max_winner_concentration_share"]) and without_best <= 0:
        failures.add(FAILURE_TAIL)

    if trades < int(plan["minimum_validation_trades"]):
        return {
            "status": "REJECTED" if FAILURE_TAIL in failures else "INCONCLUSIVE",
            "failure_categories": sorted(failures or {FAILURE_UNDERPOWERED}),
            "rejection_eligible": bool(failures),
            "protected_evidence_opened": False,
        }

    if gross <= 0:
        failures.add(FAILURE_NO_GROSS_EDGE)
    elif net <= 0:
        failures.add(FAILURE_COST_ERASED_EDGE)

    stress = screen.get("cost_stress")
    if not isinstance(stress, list) or not stress:
        raise RuntimeError("screen.cost_stress must be a non-empty list")
    frozen_multipliers = [float(x) for x in predeclaration["cost_model"]["stress_multipliers"]]
    observed: dict[float, float] = {}
    for idx, row in enumerate(stress):
        if not isinstance(row, dict):
            raise RuntimeError(f"screen.cost_stress[{idx}] must be an object")
        multiplier = _num(row.get("multiplier"), f"screen.cost_stress[{idx}].multiplier")
        value = _num(row.get("net_mean_bps"), f"screen.cost_stress[{idx}].net_mean_bps")
        if multiplier in observed:
            raise RuntimeError("screen.cost_stress contains duplicate multipliers")
        observed[multiplier] = value
    if set(observed) != set(frozen_multipliers):
        raise RuntimeError("screen.cost_stress must exactly cover frozen stress_multipliers")
    if net > 0 and any(observed[m] <= 0 for m in frozen_multipliers if m > 1.0):
        failures.add(FAILURE_COST_ERASED_EDGE)

    if plan["require_positive_validation_halves"] and any(value <= 0 for value in half_values):
        failures.add(FAILURE_REGIME_INSTABILITY)

    failures.update(_cell_failures(screen, plan))

    capacity = screen.get("capacity")
    if not isinstance(capacity, dict) or capacity.get("liquidity_capacity_pass") is not True:
        failures.add(FAILURE_CAPACITY)

    if failures:
        return {
            "status": "REJECTED",
            "failure_categories": sorted(failures),
            "rejection_eligible": True,
            "protected_evidence_opened": False,
        }

    return {
        "status": "SCREEN_PASS",
        "failure_categories": [],
        "rejection_eligible": False,
        "protected_evidence_opened": False,
    }


def _dimension_changed(parent: dict[str, Any], child: dict[str, Any], dimension: str) -> bool:
    if dimension == "economic_mechanism":
        return (
            parent.get("economic_mechanism") != child.get("economic_mechanism")
            and parent.get("hypothesis") != child.get("hypothesis")
        )
    if dimension in {"structural_component", "regime_conditioning"}:
        return parent.get("signal_rules") != child.get("signal_rules")
    if dimension == "data_source":
        return parent.get("data_contract") != child.get("data_contract")
    if dimension == "execution_premise":
        return (
            parent.get("execution_rules") != child.get("execution_rules")
            or parent.get("cost_model") != child.get("cost_model")
        )
    if dimension == "market_structure":
        return (
            parent.get("target_markets") != child.get("target_markets")
            or parent.get("target_timeframes") != child.get("target_timeframes")
        )
    return False


def _rank_successors(
    parent: dict[str, Any],
    successors: list[dict[str, Any]],
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    parent_family = parent["search_plan"]["multiple_testing_family_id"]
    parent_planned = int(parent["search_plan"]["planned_hypothesis_count"])

    for idx, proposal in enumerate(successors):
        if not isinstance(proposal, dict):
            raise RuntimeError(f"successor_proposals[{idx}] must be an object")
        raw = proposal.get("predeclaration")
        if not isinstance(raw, dict):
            raise RuntimeError(f"successor_proposals[{idx}].predeclaration must be an object")
        child = freeze_predeclaration(raw, rejected_entries=rejected_entries)
        if child["fingerprint_id"] == parent["fingerprint_id"]:
            raise RuntimeError("successor cannot reuse the failed parent fingerprint")

        dims = proposal.get("change_dimensions")
        if not isinstance(dims, list) or not dims:
            raise RuntimeError("successor change_dimensions must be a non-empty list")
        dims = [_text(value, "successor.change_dimensions") for value in dims]
        if any(value not in ALLOWED_CHANGE_DIMENSIONS for value in dims):
            raise RuntimeError("successor contains an unsupported change dimension")
        if not any(_dimension_changed(parent, child, value) for value in dims):
            raise RuntimeError("successor does not materially change its declared scientific design")

        validation = child.get("validation_plan", {})
        if validation.get("successor_uses_fresh_nonoverlapping_selection_window") is not True:
            raise RuntimeError("successor must require a fresh non-overlapping selection window")

        child_search = child["search_plan"]
        child_family = child_search["multiple_testing_family_id"]
        if child_family == parent_family:
            if int(child_search["planned_hypothesis_count"]) <= parent_planned:
                raise RuntimeError("same-family successor must increase planned_hypothesis_count")
        elif child_search.get("parent_multiple_testing_family_id") != parent_family:
            raise RuntimeError("new-family successor must retain parent_multiple_testing_family_id")

        info = _num(proposal.get("expected_information_gain"), "successor.expected_information_gain")
        plaus = _num(proposal.get("economic_plausibility"), "successor.economic_plausibility")
        ready = _num(proposal.get("data_readiness"), "successor.data_readiness")
        cost = _num(proposal.get("compute_cost"), "successor.compute_cost")
        for name, value in (
            ("expected_information_gain", info),
            ("economic_plausibility", plaus),
            ("data_readiness", ready),
            ("compute_cost", cost),
        ):
            if not 0 <= value <= 1:
                raise RuntimeError(f"successor.{name} must be in [0, 1]")
        score = 0.35 * info + 0.30 * plaus + 0.25 * ready - 0.10 * cost
        ranked.append({
            "predeclaration": child,
            "change_dimensions": sorted(set(dims)),
            "rationale": _text(proposal.get("rationale"), "successor.rationale"),
            "rank_score": round(score, 8),
        })

    ranked.sort(key=lambda row: (-row["rank_score"], row["predeclaration"]["fingerprint_id"]))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return ranked


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def build_failure_learning_artifact(
    predeclaration: dict[str, Any],
    screen: dict[str, Any],
    successor_proposals: list[dict[str, Any]] | None = None,
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    classification = classify_failure(predeclaration, screen, rejected_entries=rejected_entries)
    successors = successor_proposals or []
    if classification["status"] == "SCREEN_PASS" and successors:
        raise RuntimeError("successor generation is only valid after a failed or inconclusive screen")
    ranked = _rank_successors(
        predeclaration,
        successors,
        rejected_entries=rejected_entries,
    ) if successors else []

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "parent_fingerprint_id": predeclaration["fingerprint_id"],
        "parent_contract_sha256": predeclaration["contract_sha256"],
        "screen_id": screen["screen_id"],
        "screen_cutoff": screen["screen_cutoff"],
        "classification": classification,
        "successors": ranked,
        "research_only": True,
        "trade_authority": False,
        "broker_connected": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
    }
    artifact["artifact_sha256"] = hashlib.sha256(_canonical_bytes(artifact)).hexdigest()
    return artifact

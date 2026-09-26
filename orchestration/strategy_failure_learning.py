from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from orchestration.rejected_fingerprints import is_rejected_fingerprint
from orchestration.scientific_design_identity import strategy_behavior_sha256
from orchestration.strategy_predeclaration import freeze_predeclaration, validate_predeclaration

SCHEMA_VERSION = 1
PROJECT_MINIMUM_VALIDATION_TRADES = 20
PROJECT_MINIMUM_CELL_TRADES = 8

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

# #511 is a failure-classification/distinct-successor gate only. Experiment-value
# ranking and research-budget allocation belong to #517 and must not be smuggled
# into failure-learning proposals after outcomes are observed.
_FORBIDDEN_SUCCESSOR_ALLOCATION_FIELDS = frozenset(
    {
        "expected_information_gain",
        "economic_plausibility",
        "data_readiness",
        "compute_cost",
        "rank",
        "rank_score",
        "allocation_score",
        "priority_score",
    }
)


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


def _optional_num(
    value: Any,
    field: str,
    *,
    allow_positive_infinity: bool = False,
) -> float | None:
    """Parse an observed statistic without fabricating sparse-sample values.

    ``None`` means the statistic is mathematically undefined/unobserved for the
    available sample. Positive infinity is accepted only where the statistic
    has a well-defined no-loss interpretation (profit factor).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be numeric or null")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric or null") from exc
    if number != number or number == float("-inf"):
        raise RuntimeError(f"{field} must not be NaN or negative infinity")
    if number == float("inf") and not allow_positive_infinity:
        raise RuntimeError(f"{field} must be finite when defined")
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


def _time_window(value: Any, field: str) -> tuple[datetime, datetime]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{field} must be an object")
    start = _time(value.get("start_utc"), f"{field}.start_utc")
    end = _time(value.get("end_utc"), f"{field}.end_utc")
    if start >= end:
        raise RuntimeError(f"{field} must have start_utc < end_utc")
    return start, end


def _validation_window(screen: dict[str, Any]) -> tuple[datetime, datetime]:
    raw = screen.get("validation_window")
    start, end = _time_window(raw, "screen.validation_window")
    if not isinstance(raw, dict):  # narrow type for static readers; _time_window already checked
        raise RuntimeError("screen.validation_window must be an object")
    halves = raw.get("half_windows")
    if not isinstance(halves, list) or len(halves) != 2:
        raise RuntimeError("screen.validation_window.half_windows must contain exactly two chronological halves")
    first_start, first_end = _time_window(halves[0], "screen.validation_window.half_windows[0]")
    second_start, second_end = _time_window(halves[1], "screen.validation_window.half_windows[1]")
    if first_start != start or second_end != end or first_end != second_start:
        raise RuntimeError("validation half windows must be a non-overlapping exact chronological partition")
    if (first_end - first_start) != (second_end - second_start):
        raise RuntimeError("validation chronological halves must have equal duration")
    return start, end


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
    minimum_validation = _positive_int(
        plan["minimum_validation_trades"],
        "failure_learning_plan.minimum_validation_trades",
    )
    minimum_cell = _positive_int(plan["minimum_cell_trades"], "failure_learning_plan.minimum_cell_trades")
    if minimum_validation < PROJECT_MINIMUM_VALIDATION_TRADES:
        raise RuntimeError(
            f"project minimum validation trades is {PROJECT_MINIMUM_VALIDATION_TRADES}; "
            "a predeclaration may not lower it"
        )
    if minimum_cell < PROJECT_MINIMUM_CELL_TRADES:
        raise RuntimeError(
            f"project minimum cell trades is {PROJECT_MINIMUM_CELL_TRADES}; a predeclaration may not lower it"
        )
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
    screen_cutoff = _time(screen.get("screen_cutoff"), "screen.screen_cutoff")
    formation_cutoff = _time(predeclaration.get("formation_cutoff"), "predeclaration.formation_cutoff")
    if screen_cutoff < formation_cutoff:
        raise RuntimeError("screen_cutoff must not precede the frozen formation_cutoff")
    _, validation_end = _validation_window(screen)
    if validation_end > screen_cutoff:
        raise RuntimeError("validation window must end at or before screen_cutoff")
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
            if trades >= min_trades:
                net = _num(cell.get("net_mean_bps"), f"screen.asset_timeframe_cells[{idx}].net_mean_bps")
                eligible.append(net)
            elif cell.get("net_mean_bps") is not None:
                _num(cell.get("net_mean_bps"), f"screen.asset_timeframe_cells[{idx}].net_mean_bps")
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
            if trades >= min_trades:
                net = _num(cell.get("net_mean_bps"), f"screen.regime_cells[{idx}].net_mean_bps")
                eligible_regimes.append(net)
            elif cell.get("net_mean_bps") is not None:
                _num(cell.get("net_mean_bps"), f"screen.regime_cells[{idx}].net_mean_bps")
        if (
            len(eligible_regimes) >= 2
            and any(v > 0 for v in eligible_regimes)
            and any(v <= 0 for v in eligible_regimes)
        ):
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
    predeclaration before this screen was evaluated. Sparse samples are allowed
    to preserve mathematically undefined statistics as ``None``; they are never
    converted to fake zeros/ones merely to satisfy this schema.
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
    gross = _optional_num(validation.get("gross_mean_bps"), "screen.validation.gross_mean_bps")
    net = _optional_num(validation.get("net_mean_bps"), "screen.validation.net_mean_bps")
    profit_factor = _optional_num(
        validation.get("profit_factor"),
        "screen.validation.profit_factor",
        allow_positive_infinity=True,
    )
    if profit_factor is not None and profit_factor < 0:
        raise RuntimeError("screen.validation.profit_factor must be non-negative when defined")

    halves = validation.get("half_net_bps")
    if not isinstance(halves, list) or len(halves) != 2:
        raise RuntimeError("screen.validation.half_net_bps must contain exactly two chronological halves")
    half_values = [
        _optional_num(v, f"screen.validation.half_net_bps[{idx}]")
        for idx, v in enumerate(halves)
    ]

    risk = screen.get("risk")
    if not isinstance(risk, dict):
        raise RuntimeError("screen.risk must be an object")
    worst_event = _optional_num(risk.get("worst_event_net_bps"), "screen.risk.worst_event_net_bps")
    winner_share = _optional_num(
        risk.get("winner_concentration_share"),
        "screen.risk.winner_concentration_share",
    )
    without_best = _optional_num(
        risk.get("without_best_net_mean_bps"),
        "screen.risk.without_best_net_mean_bps",
    )
    if winner_share is not None and not 0 <= winner_share <= 1:
        raise RuntimeError("screen.risk.winner_concentration_share must be in [0, 1]")

    failures: set[str] = set()
    if worst_event is not None and worst_event <= -float(plan["catastrophic_event_loss_bps"]):
        failures.add(FAILURE_TAIL)
    if (
        winner_share is not None
        and without_best is not None
        and winner_share >= float(plan["max_winner_concentration_share"])
        and without_best <= 0
    ):
        failures.add(FAILURE_TAIL)

    # Power is checked before metrics that are mathematically undefined for
    # sparse samples. Observed catastrophic risk remains an immediate veto;
    # ordinary sparsity remains inconclusive rather than being fabricated into
    # a rejection or a passing result.
    if trades < int(plan["minimum_validation_trades"]):
        return {
            "status": "REJECTED" if FAILURE_TAIL in failures else "INCONCLUSIVE",
            "failure_categories": sorted(failures or {FAILURE_UNDERPOWERED}),
            "rejection_eligible": bool(failures),
            "protected_evidence_opened": False,
        }

    # A nominally powered total sample can still leave one chronological half
    # or an economic summary undefined. Treat that as insufficient evidence,
    # never as zero or as a pass. Any actually observed catastrophic-tail veto
    # still has rejection precedence over missing secondary summaries.
    if gross is None or net is None or profit_factor is None or any(v is None for v in half_values):
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

    if plan["require_positive_validation_halves"] and any(
        value is not None and value <= 0 for value in half_values
    ):
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


def _eligible_successors(
    parent: dict[str, Any],
    screen: dict[str, Any],
    successors: list[dict[str, Any]],
    *,
    rejected_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    parent_family = parent["search_plan"]["multiple_testing_family_id"]
    parent_planned = int(parent["search_plan"]["planned_hypothesis_count"])
    parent_behavior_digest = strategy_behavior_sha256(parent)
    seen_child_behavior_digests: set[str] = set()
    parent_validation_start, parent_validation_end = _validation_window(screen)
    parent_screen_cutoff = _time(screen.get("screen_cutoff"), "screen.screen_cutoff")

    for idx, proposal in enumerate(successors):
        if not isinstance(proposal, dict):
            raise RuntimeError(f"successor_proposals[{idx}] must be an object")
        allocation_fields = sorted(_FORBIDDEN_SUCCESSOR_ALLOCATION_FIELDS & set(proposal))
        if allocation_fields:
            raise RuntimeError(
                "successor ranking/allocation inputs belong to #517, not #511: "
                + ", ".join(allocation_fields)
            )
        raw = proposal.get("predeclaration")
        if not isinstance(raw, dict):
            raise RuntimeError(f"successor_proposals[{idx}].predeclaration must be an object")
        child = freeze_predeclaration(raw, rejected_entries=rejected_entries)
        if child["fingerprint_id"] == parent["fingerprint_id"]:
            raise RuntimeError("successor cannot reuse the failed parent fingerprint")

        child_behavior_digest = strategy_behavior_sha256(child)
        if child_behavior_digest == parent_behavior_digest:
            raise RuntimeError("successor executable behavior must differ from the failed parent")
        if child_behavior_digest in seen_child_behavior_digests:
            raise RuntimeError("successor proposals must have unique executable behavior")
        seen_child_behavior_digests.add(child_behavior_digest)

        dims = proposal.get("change_dimensions")
        if not isinstance(dims, list) or not dims:
            raise RuntimeError("successor change_dimensions must be a non-empty list")
        dims = [_text(value, "successor.change_dimensions") for value in dims]
        if any(value not in ALLOWED_CHANGE_DIMENSIONS for value in dims):
            raise RuntimeError("successor contains an unsupported change dimension")
        # Declared dimensions remain explanatory/audit metadata. Canonical
        # executable behavior identity above is the fail-closed novelty authority.
        if not any(_dimension_changed(parent, child, value) for value in dims):
            raise RuntimeError("successor does not materially change its declared scientific design")

        validation = child.get("validation_plan", {})
        if validation.get("successor_uses_fresh_nonoverlapping_selection_window") is not True:
            raise RuntimeError("successor must require a fresh non-overlapping selection window")
        successor_start, successor_end = _time_window(
            validation.get("successor_selection_window"),
            "successor.validation_plan.successor_selection_window",
        )
        overlaps_parent_validation = successor_start < parent_validation_end and successor_end > parent_validation_start
        if overlaps_parent_validation:
            raise RuntimeError("successor selection window must be disjoint from the parent validation window")
        if successor_start < parent_screen_cutoff:
            raise RuntimeError("successor fresh selection window must start at or after parent screen_cutoff")

        child_search = child["search_plan"]
        child_family = child_search["multiple_testing_family_id"]
        if child_family == parent_family:
            if int(child_search["planned_hypothesis_count"]) <= parent_planned:
                raise RuntimeError("same-family successor must increase planned_hypothesis_count")
        elif child_search.get("parent_multiple_testing_family_id") != parent_family:
            raise RuntimeError("new-family successor must retain parent_multiple_testing_family_id")

        eligible.append(
            {
                "predeclaration": child,
                "change_dimensions": sorted(set(dims)),
                "rationale": _text(proposal.get("rationale"), "successor.rationale"),
                "eligibility": "ELIGIBLE_UNRANKED",
            }
        )

    # Canonical serialization order only; fingerprint ordering grants no research
    # preference or allocation authority.
    eligible.sort(key=lambda row: row["predeclaration"]["fingerprint_id"])
    return eligible


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
    eligible = (
        _eligible_successors(
            predeclaration,
            screen,
            successors,
            rejected_entries=rejected_entries,
        )
        if successors
        else []
    )

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "parent_fingerprint_id": predeclaration["fingerprint_id"],
        "parent_contract_sha256": predeclaration["contract_sha256"],
        "screen_id": screen["screen_id"],
        "screen_cutoff": screen["screen_cutoff"],
        "classification": classification,
        "successors": eligible,
        "successor_ranking_authority": False,
        "successor_allocation_authority": False,
        "successor_allocation_owner": "ISSUE_517",
        "research_only": True,
        "trade_authority": False,
        "broker_connected": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
    }
    artifact["artifact_sha256"] = hashlib.sha256(_canonical_bytes(artifact)).hexdigest()
    return artifact

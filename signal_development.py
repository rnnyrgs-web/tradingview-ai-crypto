from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBJECTIVE_PATH = ROOT / "orchestration" / "signal_development_objective.json"
PRIMARY_OBJECTIVE_ID = "UNIVERSAL_SIGNAL_DEVELOPMENT_V1"
PRIMARY_MISSION = (
    "Continuously develop the highest achievable genuinely accurate 24h and 7d crypto "
    "BUY / SELL / WAIT signals with positive after-cost expectancy."
)
VALID_HORIZONS = {"24h", "7d", "both"}
VALID_CONCLUSIONS = {"supports", "rejects", "unresolved"}
REQUIRED_TASK_FIELDS = {
    "hypothesis",
    "predicted_mechanism",
    "target_horizon",
    "expected_signal_quality_effect",
    "evidence_needed",
    "falsification_criteria",
    "chronological_oos_requirements",
    "realistic_cost_treatment",
    "independent_sample_requirements",
    "status",
    "result",
    "evidence_conclusion",
}
HORIZON_SPAN = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


class ObjectiveError(RuntimeError):
    pass


def load_objective(path: Path = OBJECTIVE_PATH) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_objective(payload)
    return payload


def validate_objective(payload: dict) -> None:
    if payload.get("objective_id") != PRIMARY_OBJECTIVE_ID:
        raise ObjectiveError("primary signal-development objective id changed")
    if payload.get("primary_mission") != PRIMARY_MISSION:
        raise ObjectiveError("primary signal-development mission changed")
    if payload.get("optimization_target") != "genuine_forward_signal_quality":
        raise ObjectiveError("optimization target must remain genuine forward signal quality")
    invariants = payload.get("hard_invariants") or {}
    required_false = (
        "increase_heavy_concurrency_for_speed",
        "automatic_merge",
        "broker_connected",
        "reset_paper_evidence",
        "fabricate_historical_data",
        "weaken_validation_gates",
        "change_production_thresholds_to_raise_displayed_accuracy",
    )
    if any(invariants.get(key) is not False for key in required_false):
        raise ObjectiveError("unsafe universal signal-development invariant")
    if float(invariants.get("monthly_recurring_ceiling_usd", -1)) != 30.0:
        raise ObjectiveError("recurring project ceiling must remain USD 30")
    if invariants.get("insufficient_evidence") != "WAIT_RESEARCH_ONLY":
        raise ObjectiveError("insufficient evidence must fail closed")
    required_fields = set(payload.get("task_contract_required_fields") or [])
    if required_fields != REQUIRED_TASK_FIELDS:
        raise ObjectiveError("task contract schema changed")
    bottleneck = payload.get("current_bottleneck") or {}
    if bottleneck.get("id") != "ACC-002-LIQUIDITY-COVERAGE":
        raise ObjectiveError("canonical current bottleneck missing")
    if float(bottleneck.get("minimum_subset_coverage", -1)) != 0.8:
        raise ObjectiveError("ACC-002 liquidity coverage requirement changed")
    if bottleneck.get("lower_requirement_allowed") is not False:
        raise ObjectiveError("ACC-002 liquidity requirement may not be lowered")


def validate_task_contract(task: dict) -> dict:
    missing = sorted(REQUIRED_TASK_FIELDS - set(task))
    if missing:
        raise ObjectiveError(f"signal-development task missing fields: {missing}")
    if task.get("target_horizon") not in VALID_HORIZONS:
        raise ObjectiveError("invalid target_horizon")
    if task.get("evidence_conclusion") not in VALID_CONCLUSIONS:
        raise ObjectiveError("invalid evidence_conclusion")
    for key in ("hypothesis", "predicted_mechanism", "expected_signal_quality_effect", "status"):
        if not str(task.get(key) or "").strip():
            raise ObjectiveError(f"signal-development task field {key} is empty")
    for key in (
        "evidence_needed",
        "falsification_criteria",
        "chronological_oos_requirements",
        "realistic_cost_treatment",
        "independent_sample_requirements",
    ):
        if not isinstance(task.get(key), list) or not task[key]:
            raise ObjectiveError(f"signal-development task field {key} must be a non-empty list")
    return task


def priority_score(*, expected_genuine_signal_quality_impact: float, expected_information_falsification_value: float,
                   probability_actionable_evidence: float, compute_api_cost_units: float) -> float:
    values = (
        expected_genuine_signal_quality_impact,
        expected_information_falsification_value,
        probability_actionable_evidence,
    )
    if any(not math.isfinite(float(v)) or float(v) < 0 or float(v) > 1 for v in values):
        raise ObjectiveError("priority factors must be finite in [0,1]")
    cost = max(0.25, float(compute_api_cost_units))
    if not math.isfinite(cost):
        raise ObjectiveError("compute/API cost must be finite")
    return round(float(values[0]) * float(values[1]) * float(values[2]) / cost, 6)


def rank_tasks(tasks: list[dict]) -> list[dict]:
    ranked = []
    for task in tasks:
        factors = task.get("priority_factors") or {}
        row = dict(task)
        row["signal_priority_score"] = priority_score(
            expected_genuine_signal_quality_impact=factors.get("expected_genuine_signal_quality_impact", 0),
            expected_information_falsification_value=factors.get("expected_information_falsification_value", 0),
            probability_actionable_evidence=factors.get("probability_actionable_evidence", 0),
            compute_api_cost_units=factors.get("compute_api_cost_units", 1),
        )
        ranked.append(row)
    return sorted(ranked, key=lambda r: (-r["signal_priority_score"], str(r.get("id", ""))))


def objective_reference(worker_name: str, worker_class: str) -> dict:
    objective = load_objective()
    registry = objective.get("worker_registry") or {}
    if worker_class not in registry:
        raise ObjectiveError(f"worker class is not registered: {worker_class}")
    return {
        "objective_id": objective["objective_id"],
        "primary_mission": objective["primary_mission"],
        "optimization_target": objective["optimization_target"],
        "worker_name": worker_name,
        "worker_class": worker_class,
        "purpose": registry[worker_class]["purpose"],
        "signal_path": registry[worker_class]["signal_path"],
        "trade_authority": False,
        "promotion_authority": False,
    }


def _ts(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def independent_rows(rows: list[dict], horizon: str) -> list[dict]:
    span = HORIZON_SPAN[horizon]
    intervals = []
    for row in rows or []:
        if row.get("horizon") != horizon or not isinstance(row.get("correct"), bool):
            continue
        due = _ts(row.get("due_at"))
        resolved = _ts(row.get("resolved_at"))
        if due is None or resolved is None or resolved < due:
            continue
        intervals.append((due - span, due, row))
    intervals.sort(key=lambda item: (item[0], item[1]))
    selected = []
    covered_until = None
    for origin, due, row in intervals:
        if covered_until is not None and origin < covered_until:
            continue
        selected.append(row)
        covered_until = due
    return selected


def wilson_bounds(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)


def _precision(rows, direction):
    group = [r for r in rows if str(r.get("direction", "")).upper() == direction]
    correct = sum(1 for r in group if r.get("correct") is True)
    low, high = wilson_bounds(correct, len(group))
    return {"precision": round(correct / len(group), 4) if group else None, "independent_observations": len(group), "wilson_95": [low, high]}


def _after_cost(rows):
    values = []
    for row in rows:
        value = row.get("after_cost_return_pct")
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    if not values:
        return {"expectancy_pct": None, "observations": 0, "max_drawdown_pct": None}
    equity = peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {"expectancy_pct": round(sum(values) / len(values), 4), "observations": len(values), "max_drawdown_pct": round(max_dd, 4)}


def build_signal_quality_scorecard(rows: list[dict]) -> dict:
    objective = load_objective()
    horizons = {}
    for horizon in ("24h", "7d"):
        independent = independent_rows(rows, horizon)
        wait_rows = [r for r in independent if str(r.get("direction", "")).upper() == "WAIT"]
        wait_correct = sum(1 for r in wait_rows if r.get("correct") is True)
        stages = defaultdict(list)
        regimes = defaultdict(list)
        liquidities = defaultdict(list)
        for row in independent:
            stages[str(row.get("evidence_stage") or "unknown")].append(row)
            regimes[str(row.get("market_regime") or "unknown")].append(row)
            liquidities[str(row.get("liquidity_bucket") or "unknown")].append(row)
        horizons[horizon] = {
            "buy": _precision(independent, "BUY"),
            "sell": _precision(independent, "SELL"),
            "wait_quality": {"precision": round(wait_correct / len(wait_rows), 4) if wait_rows else None, "independent_observations": len(wait_rows)},
            "after_cost": _after_cost(independent),
            "independent_observation_count": len(independent),
            "regime_specific_performance": {k: _after_cost(v) for k, v in sorted(regimes.items())},
            "liquidity_specific_performance": {k: _after_cost(v) for k, v in sorted(liquidities.items())},
            "evidence_stage_performance": {k: {"count": len(v), "after_cost": _after_cost(v)} for k, v in sorted(stages.items())},
        }
    return {
        "objective_id": objective["objective_id"],
        "optimization_target": objective["optimization_target"],
        "evidence_policy": objective["scorecard"]["evidence_policy"],
        "horizons": horizons,
        "confidence_calibration": "reported separately by canonical calibration workers; never inferred from accuracy alone",
        "deterioration": "reported separately by canonical deterioration workers using independent genuine-forward evidence",
        "historical_oos_vs_genuine_forward": "must remain separated in evidence_stage_performance",
        "trade_authority": False,
        "promotion_authority": False,
    }

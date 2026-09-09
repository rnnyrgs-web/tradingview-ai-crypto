"""Deterministic research-only experiment factory.

Converts resolved-outcome diagnostics into immutable, predeclared challenger
specifications. It does not execute experiments, mutate strategies, or create
trade/promotion authority.
"""

from __future__ import annotations

import hashlib
import json
from math import isfinite

from signal_development import objective_reference, priority_score, validate_task_contract

MAX_EXPERIMENTS = 20
REQUIRED_VALIDATION = (
    "chronological_train_validation",
    "untouched_oos",
    "robustness_stability",
    "multiple_testing_firewall",
    "point_in_time_universe",
    "realistic_cost_stress",
    "genuine_forward_shadow",
)


def _finite(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _stable_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _memory_fingerprints(memory: dict | None) -> set[str]:
    lessons = memory.get("lessons") if isinstance(memory, dict) else []
    return {
        str(item.get("fingerprint"))
        for item in lessons or []
        if isinstance(item, dict) and item.get("fingerprint")
    }


def _contract(item: dict, hypothesis: str) -> dict:
    contract = {
        "hypothesis": str(item.get("hypothesis") or hypothesis),
        "predicted_mechanism": str(item.get("predicted_mechanism") or "A diagnosed independent error condition may support a restrictive filter or challenger."),
        "target_horizon": str(item.get("target_horizon") or "both"),
        "expected_signal_quality_effect": str(item.get("expected_signal_quality_effect") or "Improve genuine BUY/SELL precision or WAIT quality without sacrificing after-cost expectancy."),
        "evidence_needed": list(item.get("evidence_needed") or ["chronological backtest", "untouched OOS", "robustness/cost checks", "genuine forward evidence"]),
        "falsification_criteria": list(item.get("falsification_criteria") or ["no stable after-cost OOS improvement", "benefit disappears on independent evidence"]),
        "chronological_oos_requirements": list(item.get("chronological_oos_requirements") or ["purged chronological train/validation", "untouched OOS not reused for tuning"]),
        "realistic_cost_treatment": list(item.get("realistic_cost_treatment") or ["fees/spread/slippage before expectancy claim"]),
        "independent_sample_requirements": list(item.get("independent_sample_requirements") or ["non-overlapping full-horizon observations only"]),
        "status": "QUEUED_RESEARCH_ONLY",
        "result": None,
        "evidence_conclusion": "unresolved",
    }
    validate_task_contract(contract)
    return contract


def build_experiment_queue(diagnostics: dict, memory: dict | None = None, *, limit: int = MAX_EXPERIMENTS) -> dict:
    """Create bounded experiment specs from already-resolved diagnostic priorities."""
    priorities = diagnostics.get("research_priorities") if isinstance(diagnostics, dict) else []
    seen_lessons = _memory_fingerprints(memory)
    experiments = []
    for item in priorities or []:
        if not isinstance(item, dict) or item.get("requires_new_validation") is not True:
            continue
        dimension = str(item.get("dimension") or "unknown")
        group = str(item.get("group") or "unknown")
        hypothesis = str(item.get("research_question") or item.get("hypothesis") or "").strip()
        if not hypothesis:
            continue
        contract = _contract(item, hypothesis)
        identity = {
            "dimension": dimension,
            "group": group,
            "hypothesis": contract["hypothesis"],
            "target_horizon": contract["target_horizon"],
            "validation": REQUIRED_VALIDATION,
        }
        experiment_id = _stable_id(identity)
        lesson_fingerprint = hashlib.sha256(f"{dimension}|{group}".encode("utf-8")).hexdigest()[:24]
        wrong_rate = max(0.0, min(1.0, _finite(item.get("wrong_rate"))))
        sample_strength = max(0.0, min(1.0, int(item.get("independent_samples") or 0) / 50.0))
        repeat_penalty = 0.5 if lesson_fingerprint in seen_lessons else 1.0
        factors = {
            "expected_genuine_signal_quality_impact": round(max(0.25, wrong_rate), 4),
            "expected_information_falsification_value": round(max(0.25, sample_strength), 4),
            "probability_actionable_evidence": round(0.75 * repeat_penalty, 4),
            "compute_api_cost_units": 1.0,
        }
        information_priority = priority_score(**factors)
        experiments.append({
            "experiment_id": experiment_id,
            "dimension": dimension,
            "group": group,
            **contract,
            "source_samples": int(item.get("samples") or 0),
            "source_independent_samples": int(item.get("independent_samples") or 0),
            "source_wrong_rate": wrong_rate,
            "priority_factors": factors,
            "information_priority": information_priority,
            "repeat_penalty_applied": repeat_penalty < 1.0,
            "compute_class": "heavy_candidate",
            "required_validation": list(REQUIRED_VALIDATION),
            "automatic_execution_authority": False,
            "strategy_mutation_authority": False,
            "trade_authority": False,
            "promotion_authority": False,
        })
    experiments.sort(key=lambda row: (-row["information_priority"], -row["source_independent_samples"], row["experiment_id"]))
    bounded = experiments[: max(0, min(int(limit), MAX_EXPERIMENTS))]
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("experiment-factory", "experiment_factory"),
        "experiment_count": len(bounded),
        "experiments": bounded,
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
        "policy": "Experiment specs are hypotheses only. Ranking uses expected genuine signal-quality impact x falsification value x actionable-evidence probability / bounded compute cost. Every result still requires canonical validation.",
    }

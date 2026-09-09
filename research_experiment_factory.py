"""Deterministic research-only experiment factory.

Converts resolved-outcome diagnostics into immutable, predeclared challenger
specifications. It does not execute experiments, mutate strategies, or create
trade/promotion authority.
"""

from __future__ import annotations

import hashlib
import json
from math import isfinite

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


def build_experiment_queue(diagnostics: dict, memory: dict | None = None, *, limit: int = MAX_EXPERIMENTS) -> dict:
    """Create bounded experiment specs from already-resolved diagnostic priorities.

    Priority is intentionally descriptive. A queued experiment cannot alter live
    behavior and must pass every required validation stage before any later review.
    """
    priorities = diagnostics.get("research_priorities") if isinstance(diagnostics, dict) else []
    seen_lessons = _memory_fingerprints(memory)
    experiments = []
    for item in priorities or []:
        if not isinstance(item, dict) or item.get("requires_new_validation") is not True:
            continue
        dimension = str(item.get("dimension") or "unknown")
        group = str(item.get("group") or "unknown")
        hypothesis = str(item.get("research_question") or "").strip()
        if not hypothesis:
            continue
        identity = {
            "dimension": dimension,
            "group": group,
            "hypothesis": hypothesis,
            "validation": REQUIRED_VALIDATION,
        }
        experiment_id = _stable_id(identity)
        lesson_fingerprint = hashlib.sha256(f"{dimension}|{group}".encode("utf-8")).hexdigest()[:24]
        base_priority = max(0.0, _finite(item.get("priority_score")))
        repeat_penalty = 0.5 if lesson_fingerprint in seen_lessons else 1.0
        information_priority = round(base_priority * repeat_penalty, 4)
        experiments.append({
            "experiment_id": experiment_id,
            "dimension": dimension,
            "group": group,
            "hypothesis": hypothesis,
            "source_samples": int(item.get("samples") or 0),
            "source_wrong_rate": _finite(item.get("wrong_rate"), default=0.0),
            "information_priority": information_priority,
            "repeat_penalty_applied": repeat_penalty < 1.0,
            "compute_class": "heavy_candidate",
            "status": "QUEUED_RESEARCH_ONLY",
            "required_validation": list(REQUIRED_VALIDATION),
            "automatic_execution_authority": False,
            "strategy_mutation_authority": False,
            "trade_authority": False,
            "promotion_authority": False,
        })
    experiments.sort(key=lambda row: (-row["information_priority"], -row["source_samples"], row["experiment_id"]))
    bounded = experiments[: max(0, min(int(limit), MAX_EXPERIMENTS))]
    return {
        "ok": True,
        "research_only": True,
        "experiment_count": len(bounded),
        "experiments": bounded,
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
        "policy": "Experiment specs are hypotheses only. Heavy execution must use the bounded research pipeline and every result requires fresh canonical validation.",
    }

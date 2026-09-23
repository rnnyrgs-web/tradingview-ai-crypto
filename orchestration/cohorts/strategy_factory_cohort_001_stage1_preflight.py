"""Outcome-blind Cohort-001 Stage-1 execution-allocation preflight.

This module authenticates the frozen structural-power artifact before any future
certified Stage-1 adapter is allowed to decide which admitted candidates may have
economic outcomes read. It intentionally does not load market data, compute returns,
or grant canonical Stage-1, OOS, forward, promotion, broker, or trading authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import CANDIDATE_IDS

POWER_ARTIFACT_PATH = Path(__file__).with_name(
    "strategy_factory_cohort_001_power_feasibility.json"
)
POWER_ARTIFACT_ID = "STRATEGY-FACTORY-COHORT-001-POWER-FEASIBILITY-v1"
POWER_ARTIFACT_TYPE = "strategy_factory_stage1_preoutcome_power_feasibility"
POWER_SCOPE = "OUTCOME_BLIND_CALENDAR_AND_EXECUTION_GEOMETRY_ONLY"
PREOUTCOME_INCONCLUSIVE = "INCONCLUSIVE_POWER_PRE_OUTCOME"
SKIP_OUTCOME_SCORING = "SKIP_OUTCOME_SCORING_FOR_THIS_COHORT_CANDIDATE"
EXPECTED_BLOCKED_CANDIDATE = "DISC-WEEKEND-NORMALIZE-001-v1"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("artifact_sha256", None)
    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_power_feasibility() -> dict[str, Any]:
    """Load and fail-closed validate the exact frozen power-feasibility artifact."""
    try:
        payload = json.loads(POWER_ARTIFACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cohort-001 power-feasibility artifact unavailable") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Cohort-001 power-feasibility artifact must be an object")
    if payload.get("artifact_sha256") != _canonical_sha256(payload):
        raise RuntimeError("Cohort-001 power-feasibility artifact digest mismatch")
    if payload.get("schema_version") != 1:
        raise RuntimeError("Cohort-001 power-feasibility schema drift")
    if payload.get("artifact_type") != POWER_ARTIFACT_TYPE:
        raise RuntimeError("Cohort-001 power-feasibility type drift")
    if payload.get("artifact_id") != POWER_ARTIFACT_ID:
        raise RuntimeError("Cohort-001 power-feasibility identity drift")
    if payload.get("scope") != POWER_SCOPE:
        raise RuntimeError("Cohort-001 power-feasibility scope drift")

    candidate = payload.get("candidate")
    conclusion = payload.get("deterministic_conclusion")
    authority = payload.get("authority")
    if not isinstance(candidate, dict) or not isinstance(conclusion, dict):
        raise RuntimeError("Cohort-001 power-feasibility structure invalid")
    if candidate.get("fingerprint_id") != EXPECTED_BLOCKED_CANDIDATE:
        raise RuntimeError("unexpected Cohort-001 structurally blocked candidate")
    if candidate.get("power_gate_possible") is not False:
        raise RuntimeError("structural power artifact no longer proves impossibility")
    maximum = candidate.get("maximum_possible_validation_independent_events")
    minimum = candidate.get("minimum_independent_events_validation")
    if type(maximum) is not int or type(minimum) is not int or maximum >= minimum:
        raise RuntimeError("structural power inequality is not fail-closed")
    if conclusion.get("classification") != PREOUTCOME_INCONCLUSIVE:
        raise RuntimeError("structural power classification drift")
    if conclusion.get("stage1_allocation") != SKIP_OUTCOME_SCORING:
        raise RuntimeError("structural power allocation drift")
    if conclusion.get("economic_evidence") != "NONE_OPENED":
        raise RuntimeError("power artifact must remain pre-outcome")
    if conclusion.get("family_evidence") != "UNDERPOWERED_STRUCTURAL_NOT_ECONOMIC_REJECTION":
        raise RuntimeError("power artifact may not create economic rejection authority")
    if conclusion.get("threshold_or_window_change_allowed") is not False:
        raise RuntimeError("post-hoc threshold/window rescue must remain forbidden")
    if conclusion.get("post_hoc_validation_extension_allowed") is not False:
        raise RuntimeError("post-hoc validation extension must remain forbidden")

    expected_authority = {
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
        "rejected_exact_memory_mutated": False,
        "rejected_semantic_memory_mutated": False,
    }
    if authority != expected_authority:
        raise RuntimeError("Cohort-001 power-feasibility authority drift")
    return payload


def executable_candidate_ids() -> tuple[str, ...]:
    """Return the exact admitted candidates still eligible for Cohort-001 economics.

    Admission history is not rewritten. This is an execution-allocation overlay formed
    strictly from outcome-blind structural power evidence.
    """
    payload = load_power_feasibility()
    blocked = payload["candidate"]["fingerprint_id"]
    eligible = tuple(candidate_id for candidate_id in CANDIDATE_IDS if candidate_id != blocked)
    if len(CANDIDATE_IDS) != 6 or len(eligible) != 5:
        raise RuntimeError("unexpected Cohort-001 candidate allocation cardinality")
    return eligible


def assert_economic_outcome_read_allowed(candidate_id: str) -> None:
    """Fail before any Cohort-001 economic read for structurally underpowered work.

    This function grants no positive authority by itself. Returning only means the
    candidate is not eliminated by this one frozen pre-outcome power overlay; all
    parent admission, certified-data, exact-head CI/review, chronology, OOS/forward,
    and authority gates remain separately mandatory.
    """
    if candidate_id not in CANDIDATE_IDS:
        raise ValueError("candidate is not Cohort-001 admitted")
    payload = load_power_feasibility()
    if candidate_id == payload["candidate"]["fingerprint_id"]:
        raise RuntimeError(
            "Cohort-001 economic outcome read forbidden: candidate is "
            "INCONCLUSIVE_POWER_PRE_OUTCOME"
        )

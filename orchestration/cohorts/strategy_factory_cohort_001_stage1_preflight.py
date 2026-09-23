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
STAGE1_RUNNER_PATH = Path(__file__).with_name("strategy_factory_cohort_001_stage1_runner.py")
STAGE1_EXECUTION_CONTRACT_PATH = Path(__file__).with_name(
    "strategy_factory_cohort_001_stage1_execution_contract.json"
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


def _git_blob_sha1(raw: bytes) -> str:
    """Return Git's blob object id for exact repository bytes."""
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()  # nosec B324 - Git object identity only


def _load_source_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Cohort-001 {label} source unavailable") from exc


def _validate_source_contracts(payload: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Authenticate structural-power proof inputs against the executable sources."""
    sources = payload.get("source_contracts")
    if not isinstance(sources, dict):
        raise RuntimeError("Cohort-001 power-feasibility source contracts missing")

    expected_runner_sha = sources.get("stage1_runner_blob_sha")
    expected_execution_sha = sources.get("stage1_execution_contract_blob_sha")
    if not isinstance(expected_runner_sha, str) or len(expected_runner_sha) != 40:
        raise RuntimeError("Cohort-001 Stage-1 runner source blob identity invalid")
    if not isinstance(expected_execution_sha, str) or len(expected_execution_sha) != 40:
        raise RuntimeError("Cohort-001 Stage-1 execution source blob identity invalid")

    runner_raw = _load_source_bytes(STAGE1_RUNNER_PATH, "Stage-1 runner")
    execution_raw = _load_source_bytes(
        STAGE1_EXECUTION_CONTRACT_PATH,
        "Stage-1 execution contract",
    )
    if _git_blob_sha1(runner_raw) != expected_runner_sha:
        raise RuntimeError("Cohort-001 Stage-1 runner source blob mismatch")
    if _git_blob_sha1(execution_raw) != expected_execution_sha:
        raise RuntimeError("Cohort-001 Stage-1 execution source blob mismatch")

    try:
        execution_contract = json.loads(execution_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cohort-001 Stage-1 execution contract is invalid JSON") from exc
    if not isinstance(execution_contract, dict):
        raise RuntimeError("Cohort-001 Stage-1 execution contract must be an object")

    try:
        contract_minimum = execution_contract["global_numerical_semantics"][
            "minimum_sample_gate"
        ]["validation_independent_events"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Cohort-001 Stage-1 validation minimum missing from execution contract"
        ) from exc
    artifact_minimum = candidate.get("minimum_independent_events_validation")
    if type(contract_minimum) is not int or type(artifact_minimum) is not int:
        raise RuntimeError("Cohort-001 Stage-1 validation minimum must be an integer")
    if contract_minimum != artifact_minimum:
        raise RuntimeError(
            "Cohort-001 structural-power validation minimum diverges from execution contract"
        )


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

    _validate_source_contracts(payload, candidate)

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

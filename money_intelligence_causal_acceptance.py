"""Sealed exact-deployment acceptance for the causal-memory research loop."""

from __future__ import annotations

import os
from typing import Any

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
)
from money_intelligence_causal_runtime import causal_mission_feedback
from money_intelligence_causal_supabase import SupabaseCausalMemory


CONTRADICTION_ID = "MI-RUNTIME-ACCEPT-CONTRADICTION"
DECAY_ID = "MI-RUNTIME-ACCEPT-DECAY"
TARGET_IDS = {CONTRADICTION_ID, DECAY_ID}
SUPPORT_AS_OF = "2025-01-03T01:00:00Z"
CONTRADICTION_AS_OF = "2025-01-05T01:00:00Z"
DECAY_AS_OF = "2025-06-01T00:00:00Z"


def _deployed_sha() -> str:
    value = os.getenv("RENDER_GIT_COMMIT", "").strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("valid deployed SHA is required for causal runtime acceptance")
    return value


def _observation(
    observation_id: str,
    metric_name: str,
    value: float,
    *,
    observed_at: str,
    available_at: str,
    retrieved_at: str,
) -> PointInTimeObservation:
    return PointInTimeObservation(
        observation_id=observation_id,
        metric_name=metric_name,
        value=value,
        unit="ratio",
        observed_at=observed_at,
        available_at=available_at,
        retrieved_at=retrieved_at,
        source_id="sealed-runtime-acceptance",
        subject_id="RUNTIME-ACCEPTANCE-NOT-A-MARKET-SIGNAL",
        currency="ratio",
        measurement_window_hours=72,
        venue="sealed-fixture",
        max_age_hours=72,
        revision_id="v1",
        provenance_uri=f"repository://causal-runtime-acceptance/{observation_id}",
    )


def _hypothesis(hypothesis_id: str, *, suffix: str) -> FrozenHypothesis:
    return FrozenHypothesis(
        hypothesis_id=hypothesis_id,
        statement=(
            f"Sealed acceptance mechanism {suffix} must enter research ranking only "
            "while confirmatory evidence remains qualified."
        ),
        mechanism_chain=("sealed_observation", "frozen_test", suffix),
        direction="positive",
        horizon_hours=72,
        falsifier="sealed matched-control effect is non-positive",
        matched_controls=("sealed_market_beta", "sealed_volatility_regime"),
        lanes=("big_move", "strategy_component"),
        created_at="2025-01-02T00:00:00Z",
        source_observation_ids=("accept-formation",),
        family_id=f"MI-RUNTIME-ACCEPT-{suffix.upper()}",
        evaluation_method="sealed_matched_control_mean_difference_v1",
        family_size=2,
        alpha=0.05,
    )


def _register_contract(memory: CausalRepricingMemory) -> None:
    observations = (
        _observation(
            "accept-formation",
            "sealed_flow_float",
            0.05,
            observed_at="2025-01-01T00:00:00Z",
            available_at="2025-01-01T01:00:00Z",
            retrieved_at="2025-01-01T02:00:00Z",
        ),
        _observation(
            "accept-c-support-outcome",
            "sealed_forward_return_72h",
            0.08,
            observed_at="2025-01-02T01:00:00Z",
            available_at="2025-01-02T04:00:00Z",
            retrieved_at="2025-01-02T05:00:00Z",
        ),
        _observation(
            "accept-c-support-control",
            "sealed_control_return_72h",
            0.01,
            observed_at="2025-01-02T01:00:00Z",
            available_at="2025-01-02T04:00:00Z",
            retrieved_at="2025-01-02T05:00:00Z",
        ),
        _observation(
            "accept-c-adverse-outcome",
            "sealed_forward_return_72h",
            -0.08,
            observed_at="2025-01-04T01:00:00Z",
            available_at="2025-01-04T04:00:00Z",
            retrieved_at="2025-01-04T05:00:00Z",
        ),
        _observation(
            "accept-c-adverse-control",
            "sealed_control_return_72h",
            0.01,
            observed_at="2025-01-04T01:00:00Z",
            available_at="2025-01-04T04:00:00Z",
            retrieved_at="2025-01-04T05:00:00Z",
        ),
        _observation(
            "accept-d-support-outcome",
            "sealed_forward_return_72h",
            0.09,
            observed_at="2025-01-02T01:00:00Z",
            available_at="2025-01-02T04:00:00Z",
            retrieved_at="2025-01-02T05:00:00Z",
        ),
        _observation(
            "accept-d-support-control",
            "sealed_control_return_72h",
            0.01,
            observed_at="2025-01-02T01:00:00Z",
            available_at="2025-01-02T04:00:00Z",
            retrieved_at="2025-01-02T05:00:00Z",
        ),
    )
    for observation in observations:
        memory.register_observation(observation)
    hypotheses = (
        _hypothesis(CONTRADICTION_ID, suffix="contradiction"),
        _hypothesis(DECAY_ID, suffix="decay"),
    )
    for hypothesis in hypotheses:
        memory.register_hypothesis(hypothesis)
    memory.record_evidence(
        EvidenceEvent(
            event_id="MI-RUNTIME-ACCEPT-CONTRADICTION-SUPPORT",
            hypothesis_id=CONTRADICTION_ID,
            evaluated_at="2025-01-03T00:00:00Z",
            kind="support",
            matched_controls=hypotheses[0].matched_controls,
            outcome_observation_ids=("accept-c-support-outcome",),
            control_observation_ids=("accept-c-support-control",),
            evaluation_method=hypotheses[0].evaluation_method,
            sample_size=40,
            p_value=0.01,
        )
    )
    memory.record_evidence(
        EvidenceEvent(
            event_id="MI-RUNTIME-ACCEPT-CONTRADICTION-ADVERSE",
            hypothesis_id=CONTRADICTION_ID,
            evaluated_at="2025-01-05T00:00:00Z",
            kind="contradiction",
            matched_controls=hypotheses[0].matched_controls,
            outcome_observation_ids=("accept-c-adverse-outcome",),
            control_observation_ids=("accept-c-adverse-control",),
            evaluation_method=hypotheses[0].evaluation_method,
            sample_size=40,
            p_value=0.01,
        )
    )
    memory.record_evidence(
        EvidenceEvent(
            event_id="MI-RUNTIME-ACCEPT-DECAY-SUPPORT",
            hypothesis_id=DECAY_ID,
            evaluated_at="2025-01-03T00:00:00Z",
            kind="support",
            matched_controls=hypotheses[1].matched_controls,
            outcome_observation_ids=("accept-d-support-outcome",),
            control_observation_ids=("accept-d-support-control",),
            evaluation_method=hypotheses[1].evaluation_method,
            sample_size=40,
            p_value=0.01,
        )
    )


def _target_state(memory: CausalRepricingMemory) -> dict[str, Any]:
    return {
        "hypotheses": {
            key: memory.hypotheses[key].fingerprint
            for key in sorted(TARGET_IDS)
            if key in memory.hypotheses
        },
        "events": {
            key: event.fingerprint
            for key, event in sorted(memory.events.items())
            if event.hypothesis_id in TARGET_IDS
        },
    }


def _target_missions(feedback: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        mission
        for mission in feedback.get("missions", [])
        if mission.get("causal_evidence", {}).get("hypothesis_id") in TARGET_IDS
    ]


def _execute_acceptance(deployed_sha: str) -> dict[str, Any]:
    store = SupabaseCausalMemory()
    try:
        store.load()
    except CausalMemoryError as exc:
        if "not initialized" not in str(exc):
            raise
        store.initialize(CausalRepricingMemory())

    store.transact(_register_contract)
    after_first = SupabaseCausalMemory().load()
    first_document = after_first.to_document()
    first_target = _target_state(after_first)

    store.transact(_register_contract)
    after_replay = SupabaseCausalMemory().load()
    replay_document = after_replay.to_document()
    replay_target = _target_state(after_replay)
    restarted = SupabaseCausalMemory().load()

    support = causal_mission_feedback(as_of=SUPPORT_AS_OF, store=SupabaseCausalMemory())
    contradicted = causal_mission_feedback(
        as_of=CONTRADICTION_AS_OF, store=SupabaseCausalMemory()
    )
    decayed = causal_mission_feedback(as_of=DECAY_AS_OF, store=SupabaseCausalMemory())
    current = causal_mission_feedback(store=SupabaseCausalMemory())
    support_rows = _target_missions(support)
    support_ids = sorted(
        {row["causal_evidence"]["hypothesis_id"] for row in support_rows}
    )
    contradiction_rows = _target_missions(contradicted)
    decay_rows = _target_missions(decayed)
    current_rows = _target_missions(current)

    if (
        support.get("status") != "READY"
        or len(support_rows) != 4
        or support_ids != sorted(TARGET_IDS)
        or any(
            row["causal_evidence"]["hypothesis_id"] == CONTRADICTION_ID
            for row in contradiction_rows
        )
        or any(
            row["causal_evidence"]["hypothesis_id"] == DECAY_ID
            for row in decay_rows
        )
        or current_rows
        or first_target != replay_target
        or first_document != replay_document
        or restarted.to_document() != replay_document
    ):
        raise ValueError("causal runtime acceptance invariant failed")

    return {
        "ok": True,
        "schema_version": 1,
        "deployed_sha": deployed_sha,
        "persistence": {
            "target_state_digest_after_first": first_document["content_digest"],
            "target_state_digest_after_replay": replay_document["content_digest"],
            "replay_idempotent": first_document == replay_document,
            "restart_equal": restarted.to_document() == replay_document,
            "target_hypothesis_count": len(first_target["hypotheses"]),
            "target_event_count": len(first_target["events"]),
        },
        "transitions": {
            "support_stage": {
                "mission_count": len(support_rows),
                "hypothesis_ids": support_ids,
                "mission_ids": sorted(row["mission_id"] for row in support_rows),
            },
            "contradiction_removed": not any(
                row["causal_evidence"]["hypothesis_id"] == CONTRADICTION_ID
                for row in contradiction_rows
            ),
            "decay_removed": not any(
                row["causal_evidence"]["hypothesis_id"] == DECAY_ID
                for row in decay_rows
            ),
            "current_acceptance_mission_count": len(current_rows),
        },
        "safety": {
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "oos_opening_authority": False,
            "broker_connected": False,
        },
    }


def run_causal_runtime_acceptance() -> dict[str, Any]:
    """Persist and replay a sealed synthetic contract through live durable paths."""
    deployed_sha = _deployed_sha()
    try:
        return _execute_acceptance(deployed_sha)
    except Exception as exc:
        raise ValueError("causal runtime acceptance failed") from exc

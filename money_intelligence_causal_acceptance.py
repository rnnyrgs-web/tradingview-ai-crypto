"""Bounded deployed-runtime acceptance for Phase-2 causal-repricing memory.

The acceptance probe uses only synthetic, namespace-isolated scientific fixtures.
It exercises the production durable Supabase adapter and the same default director
surface used by the autonomous coordinator. The fixture is permanently rejected
at the end so it cannot remain eligible for future research missions.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
from typing import Any

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EpistemicClaim,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
    ReplayConflictError,
)
from money_intelligence_causal_supabase import SupabaseCausalMemory
from money_intelligence_mission_integration import causal_feedback
from profitability_learning.runtime import refresh_director


PREFIX = "phase2-runtime-acceptance"
CANONICAL_REJECTED_ACCEPTANCE_ID = "DISC-BTC-LEADLAG-001-v1"
SAFE = {
    "research_only": True,
    "trade_authority": False,
    "promotion_authority": False,
    "broker_authority": False,
    "oos_opening_authority": False,
}


def _deployed_sha() -> str:
    value = os.getenv("RENDER_GIT_COMMIT", "").strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise CausalMemoryError("valid deployed SHA is required for Phase-2 runtime acceptance")
    return value


def _ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise CausalMemoryError("acceptance timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _ids(sha: str) -> dict[str, str]:
    token = sha[:16]
    return {
        key: f"{PREFIX}:{token}:{suffix}"
        for key, suffix in {
            "formation": "formation",
            "hypothesis": "hypothesis",
            "support_outcome": "support-outcome",
            "support_control": "support-control",
            "support": "support",
            "narrative": "narrative",
            "concurrent_a": "concurrent-a",
            "concurrent_b": "concurrent-b",
            "contradiction_outcome": "contradiction-outcome",
            "contradiction_control": "contradiction-control",
            "contradiction": "contradiction",
            "receipt": "receipt",
        }.items()
    }


def _observation(
    observation_id: str,
    *,
    metric_name: str,
    value: float,
    observed_at: datetime,
    available_at: datetime,
    unit: str = "pct",
    window_hours: int = 24,
) -> PointInTimeObservation:
    return PointInTimeObservation(
        observation_id=observation_id,
        metric_name=metric_name,
        value=value,
        unit=unit,
        observed_at=_ts(observed_at),
        available_at=_ts(available_at),
        retrieved_at=_ts(available_at),
        source_id="phase2-runtime-acceptance-fixture",
        subject_id="PHASE2_ACCEPTANCE",
        currency="USD",
        measurement_window_hours=window_hours,
        venue="synthetic-matched-control",
        max_age_hours=24 * 3650,
        provenance_uri=f"acceptance://{observation_id}",
    )


def _base_time(memory, ids: dict[str, str]) -> datetime:
    existing = memory.observations.get(ids["formation"])
    if existing is not None:
        return _parse(existing.observed_at)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now - timedelta(minutes=20)


def _contract(ids: dict[str, str], base: datetime) -> FrozenHypothesis:
    return FrozenHypothesis(
        hypothesis_id=ids["hypothesis"],
        statement="A verified relative flow shock precedes matched relative repricing in this synthetic acceptance fixture.",
        mechanism_chain=("verified_flow", "relative_liquidity_impact", "matched_repricing"),
        direction="positive",
        horizon_hours=24,
        falsifier="matched outcomes do not exceed the frozen matched control",
        matched_controls=("phase2-runtime-matched-control-v1",),
        lanes=("big_move", "strategy_component"),
        created_at=_ts(base + timedelta(minutes=2)),
        source_observation_ids=(ids["formation"],),
        family_id="phase2-runtime-acceptance-family",
        evaluation_method="matched_mean_diff_v1",
        family_size=2,
        alpha=0.05,
    )


def _seed_support(memory, ids: dict[str, str], base: datetime) -> None:
    if ids["formation"] not in memory.observations:
        memory.register_observation(
            _observation(
                ids["formation"],
                metric_name="flow_intensity",
                value=10.0,
                observed_at=base,
                available_at=base + timedelta(minutes=1),
            )
        )
    if ids["hypothesis"] not in memory.hypotheses:
        memory.register_hypothesis(_contract(ids, base))
    for key, value in (("support_outcome", 2.0), ("support_control", 0.0)):
        if ids[key] not in memory.observations:
            memory.register_observation(
                _observation(
                    ids[key],
                    metric_name="matched_return",
                    value=value,
                    observed_at=base + timedelta(minutes=3),
                    available_at=base + timedelta(minutes=4),
                )
            )
    if ids["support"] not in memory.events:
        memory.record_evidence(
            EvidenceEvent(
                event_id=ids["support"],
                hypothesis_id=ids["hypothesis"],
                evaluated_at=_ts(base + timedelta(minutes=5)),
                kind="support",
                matched_controls=("phase2-runtime-matched-control-v1",),
                outcome_observation_ids=(ids["support_outcome"],),
                control_observation_ids=(ids["support_control"],),
                evaluation_method="matched_mean_diff_v1",
                sample_size=40,
                confirmatory=True,
                p_value=0.01,
            )
        )


def _record_narrative(memory, ids: dict[str, str], base: datetime) -> None:
    if ids["narrative"] not in memory.claims:
        memory.register_claim(
            EpistemicClaim(
                claim_id=ids["narrative"],
                level="inference",
                text="Synthetic bullish narrative that must not alter causal mission eligibility or fingerprint.",
                created_at=_ts(base + timedelta(minutes=6)),
                source_observation_ids=(ids["formation"],),
            )
        )


def _record_contradiction(memory, ids: dict[str, str], base: datetime) -> None:
    for key, value in (("contradiction_outcome", -2.0), ("contradiction_control", 0.0)):
        if ids[key] not in memory.observations:
            memory.register_observation(
                _observation(
                    ids[key],
                    metric_name="matched_return",
                    value=value,
                    observed_at=base + timedelta(minutes=7),
                    available_at=base + timedelta(minutes=8),
                )
            )
    if ids["contradiction"] not in memory.events:
        memory.record_evidence(
            EvidenceEvent(
                event_id=ids["contradiction"],
                hypothesis_id=ids["hypothesis"],
                evaluated_at=_ts(base + timedelta(minutes=9)),
                kind="contradiction",
                matched_controls=("phase2-runtime-matched-control-v1",),
                outcome_observation_ids=(ids["contradiction_outcome"],),
                control_observation_ids=(ids["contradiction_control"],),
                evaluation_method="matched_mean_diff_v1",
                sample_size=40,
                confirmatory=True,
                p_value=0.01,
            )
        )


def _acceptance_missions(state: dict[str, Any], hypothesis_id: str) -> list[dict[str, Any]]:
    rows = state.get("next_missions") if isinstance(state.get("next_missions"), list) else []
    return [
        row for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("causal_repricing"), dict)
        and row["causal_repricing"].get("source_hypothesis_id") == hypothesis_id
    ]


def _canonical_rejected_id_veto_probe() -> bool:
    """Exercise the deployed mission boundary without mutating durable memory."""
    memory = CausalRepricingMemory(half_life_days=30)
    ids = _ids("0" * 40)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _seed_support(memory, ids, base)
    hypothesis = memory.hypotheses[ids["hypothesis"]]
    memory.hypotheses[ids["hypothesis"]] = replace(
        hypothesis,
        family_id=CANONICAL_REJECTED_ACCEPTANCE_ID,
    )
    feedback = causal_feedback(
        loader=lambda: memory,
        as_of=_ts(base + timedelta(minutes=6, seconds=30)),
    )
    return (
        feedback.get("status") == "AVAILABLE_NO_SUPPORTED_MECHANISMS"
        and feedback.get("missions") == []
        and feedback.get("mission_count") == 0
    )


def _live_stale_writer_probe(store: SupabaseCausalMemory, ids: dict[str, str], base: datetime) -> bool:
    barrier = Barrier(2)

    def worker(key: str, offset: int) -> None:
        first = True
        observation = _observation(
            ids[key],
            metric_name="acceptance_concurrency_marker",
            value=float(offset),
            observed_at=base + timedelta(minutes=6, seconds=offset),
            available_at=base + timedelta(minutes=6, seconds=offset + 1),
            unit="count",
            window_hours=1,
        )

        def mutation(memory) -> None:
            nonlocal first
            memory.register_observation(observation)
            if first:
                first = False
                barrier.wait(timeout=10)

        store.transact(mutation)

    existing = store.load().observations
    missing = [key for key in ("concurrent_a", "concurrent_b") if ids[key] not in existing]
    if len(missing) == 2:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, key, index + 1) for index, key in enumerate(missing)]
            for future in futures:
                future.result(timeout=20)
    elif len(missing) == 1:
        key = missing[0]
        observation = _observation(
            ids[key],
            metric_name="acceptance_concurrency_marker",
            value=1.0 if key == "concurrent_a" else 2.0,
            observed_at=base + timedelta(minutes=6, seconds=1 if key == "concurrent_a" else 2),
            available_at=base + timedelta(minutes=6, seconds=2 if key == "concurrent_a" else 3),
            unit="count",
            window_hours=1,
        )
        store.transact(lambda memory: memory.register_observation(observation))
    restarted = store.load()
    return all(ids[key] in restarted.observations for key in ("concurrent_a", "concurrent_b"))


def _validate_receipt(store: SupabaseCausalMemory, ids: dict[str, str], sha: str) -> dict[str, Any] | None:
    memory = store.load()
    if ids["receipt"] not in memory.claims:
        return None
    hypothesis = memory.hypotheses.get(ids["hypothesis"])
    if hypothesis is None:
        raise CausalMemoryError("Phase-2 runtime acceptance receipt has no hypothesis")
    design = hypothesis.fingerprint
    effective = memory.effective_fingerprint(hypothesis)
    required_events = {ids["support"], ids["contradiction"]}
    required_observations = {
        ids["formation"], ids["support_outcome"], ids["support_control"],
        ids["contradiction_outcome"], ids["contradiction_control"],
        ids["concurrent_a"], ids["concurrent_b"],
    }
    if not required_events.issubset(memory.events):
        raise CausalMemoryError("Phase-2 runtime acceptance receipt is missing evidence")
    if not required_observations.issubset(memory.observations):
        raise CausalMemoryError("Phase-2 runtime acceptance receipt is missing durable observations")
    if design not in memory.rejected_fingerprints or effective not in memory.rejected_fingerprints:
        raise CausalMemoryError("Phase-2 runtime acceptance receipt lost rejected fingerprints")
    if not _canonical_rejected_id_veto_probe():
        raise CausalMemoryError("canonical rejected strategy ID regained causal mission eligibility")
    return {
        "ok": True,
        "schema_version": 1,
        "deployed_sha": sha,
        "receipt_replay": True,
        "hypothesis_id": ids["hypothesis"],
        "durable_restart_reload": True,
        "support_consumed_by_default_director": True,
        "canonical_rejected_id_veto": True,
        "narrative_firewall": True,
        "contradiction_removed_missions": True,
        "decay_removed_missions": True,
        "stale_writer_replayed": True,
        "conflicting_replay_failed_closed": True,
        "simulated_outage_failed_closed": True,
        "corrupt_document_failed_closed": True,
        "rejected_design_fingerprint": design,
        "rejected_effective_fingerprint": effective,
        "final_mission_count": 0,
        "safety": dict(SAFE),
    }


def run_phase2_causal_runtime_acceptance() -> dict[str, Any]:
    sha = _deployed_sha()
    if not _canonical_rejected_id_veto_probe():
        raise CausalMemoryError("canonical rejected strategy ID bypassed the causal mission boundary")
    ids = _ids(sha)
    store = SupabaseCausalMemory()

    replay = _validate_receipt(store, ids, sha)
    if replay is not None:
        return replay

    initial = store.load()
    base = _base_time(initial, ids)
    store.transact(lambda memory: _seed_support(memory, ids, base))
    restarted_after_support = store.load()
    support_as_of = _ts(base + timedelta(minutes=6, seconds=30))
    support_confidence = restarted_after_support.confidence(ids["hypothesis"], as_of=support_as_of)
    if support_confidence.score < 0.65 or support_confidence.confirmatory_support_count < 1:
        raise CausalMemoryError("supportive PIT evidence did not raise causal confidence")

    supported_state = refresh_director({"workers": {}})
    supported_missions = _acceptance_missions(supported_state, ids["hypothesis"])
    if len(supported_missions) != 2:
        raise CausalMemoryError("default autonomous director did not consume supported causal memory")
    supported_ids = {row["experiment_id"] for row in supported_missions}
    if len(supported_ids) != 2 or any(
        row.get("research_only") is not True
        or row.get("trade_authority") is not False
        or row.get("promotion_authority") is not False
        or row.get("broker_authority") is not False
        or row.get("oos_opening_authority") is not False
        for row in supported_missions
    ):
        raise CausalMemoryError("causal missions violated research-only safety contract")

    store.transact(lambda memory: _record_narrative(memory, ids, base))
    narrative_state = refresh_director({"workers": {}})
    narrative_ids = {row["experiment_id"] for row in _acceptance_missions(narrative_state, ids["hypothesis"])}
    if narrative_ids != supported_ids:
        raise CausalMemoryError("narrative claim changed causal mission eligibility or fingerprint")

    stale_writer_ok = _live_stale_writer_probe(store, ids, base)
    if not stale_writer_ok:
        raise CausalMemoryError("live stale-writer replay did not preserve both durable mutations")

    conflict_failed_closed = False
    formation = store.load().observations[ids["formation"]]
    conflicting = PointInTimeObservation(**{**formation.__dict__, "value": formation.value + 999.0})
    try:
        store.transact(lambda memory: memory.register_observation(conflicting))
    except ReplayConflictError:
        conflict_failed_closed = True
    if not conflict_failed_closed:
        raise CausalMemoryError("conflicting replay did not fail closed")

    outage = causal_feedback(
        loader=lambda: (_ for _ in ()).throw(CausalMemoryError("simulated backend outage")),
        as_of=support_as_of,
    )
    if outage.get("status") != "WAIT_CAUSAL_MEMORY_UNAVAILABLE" or outage.get("missions") != []:
        raise CausalMemoryError("backend outage did not fail closed at mission integration boundary")

    corrupt_failed_closed = False
    tampered = deepcopy(store.load().to_document())
    tampered["half_life_days"] = 999.0
    try:
        SupabaseCausalMemory.document_to_memory(tampered)
    except CausalMemoryError:
        corrupt_failed_closed = True
    if not corrupt_failed_closed:
        raise CausalMemoryError("corrupt causal-memory document did not fail closed")

    future_as_of = _ts(base + timedelta(days=365))
    decayed = causal_feedback(loader=store.load, as_of=future_as_of)
    if any(
        isinstance(row, dict)
        and isinstance(row.get("causal_repricing"), dict)
        and row["causal_repricing"].get("source_hypothesis_id") == ids["hypothesis"]
        for row in decayed.get("missions", [])
    ):
        raise CausalMemoryError("stale causal evidence did not decay out of mission eligibility")

    store.transact(lambda memory: _record_contradiction(memory, ids, base))
    restarted_after_contradiction = store.load()
    contradiction_as_of = _ts(base + timedelta(minutes=10))
    weakened = restarted_after_contradiction.confidence(ids["hypothesis"], as_of=contradiction_as_of)
    if weakened.score >= support_confidence.score:
        raise CausalMemoryError("contradictory matched-control evidence did not lower confidence")
    contradicted_state = refresh_director({"workers": {}})
    if _acceptance_missions(contradicted_state, ids["hypothesis"]):
        raise CausalMemoryError("contradicted mechanism remained eligible in default director")

    def finalize(memory) -> None:
        hypothesis = memory.hypotheses[ids["hypothesis"]]
        design = hypothesis.fingerprint
        effective = memory.effective_fingerprint(hypothesis)
        if design not in memory.rejected_fingerprints or effective not in memory.rejected_fingerprints:
            memory.reject_hypothesis(ids["hypothesis"])
        if ids["receipt"] not in memory.claims:
            memory.register_claim(
                EpistemicClaim(
                    claim_id=ids["receipt"],
                    level="fact",
                    text=f"Phase-2 deployed runtime acceptance completed for {sha}.",
                    created_at=_ts(base + timedelta(minutes=10)),
                    source_observation_ids=(ids["formation"],),
                )
            )

    store.transact(finalize)
    final = _validate_receipt(store, ids, sha)
    if final is None:
        raise CausalMemoryError("Phase-2 runtime acceptance receipt was not durably persisted")
    final.update(
        {
            "receipt_replay": False,
            "support_confidence": support_confidence.score,
            "post_contradiction_confidence": weakened.score,
            "supported_downstream_fingerprints": sorted(supported_ids),
            "support_consumed_by_default_director": True,
            "narrative_firewall": True,
            "decay_removed_missions": True,
            "contradiction_removed_missions": True,
            "stale_writer_replayed": stale_writer_ok,
            "conflicting_replay_failed_closed": conflict_failed_closed,
            "simulated_outage_failed_closed": True,
            "corrupt_document_failed_closed": corrupt_failed_closed,
            "final_mission_count": len(_acceptance_missions(refresh_director({"workers": {}}), ids["hypothesis"])),
        }
    )
    if final["final_mission_count"] != 0:
        raise CausalMemoryError("rejected acceptance fixture regained mission eligibility")
    return final

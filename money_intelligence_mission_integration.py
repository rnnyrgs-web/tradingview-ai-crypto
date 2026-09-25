"""Research-only causal-memory to research-mission adapter.

Consumes only structured point-in-time evidence that clears the existing
CausalRepricingMemory scientific gate. Narrative-only claims are not inputs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Callable

from money_intelligence_causal_memory import CausalMemoryError, CausalRepricingMemory
from orchestration.rejected_fingerprints import load_rejected_fingerprints
from research_director import build_mission

SCHEMA_VERSION = 1
SAFE = {
    "research_only": True,
    "trade_authority": False,
    "promotion_authority": False,
    "broker_authority": False,
    "oos_opening_authority": False,
}


def _finite_priority(row: object) -> float | None:
    if not isinstance(row, dict):
        return None
    raw = row.get("priority", 0.0)
    if isinstance(raw, bool):
        return None
    try:
        priority = float(raw)
    except (TypeError, ValueError):
        return None
    return priority if math.isfinite(priority) else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(artifact: dict[str, object], lane: str) -> str:
    events = artifact.get("evidence_events")
    if not isinstance(events, list) or not events:
        raise CausalMemoryError("supported artifact has no evidence events")
    event_fps = []
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("event_fingerprint"), str):
            raise CausalMemoryError("malformed evidence provenance")
        event_fps.append(event["event_fingerprint"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "source_hypothesis_fingerprint": artifact.get("hypothesis_fingerprint"),
        "design_fingerprint": artifact.get("design_fingerprint"),
        "formation_provenance_fingerprints": artifact.get("formation_provenance_fingerprints"),
        "evidence_event_fingerprints": event_fps,
        "frozen_test_contract": artifact.get("frozen_test_contract"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "mi-downstream-v1:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_supported_missions(memory: CausalRepricingMemory, *, as_of: str) -> list[dict[str, Any]]:
    rejected_ids = {
        str(entry["fingerprint_id"])
        for entry in load_rejected_fingerprints()
        if entry.get("do_not_resubmit_same_fingerprint") is True
    }
    missions: list[dict[str, Any]] = []
    for hypothesis_id in sorted(memory.hypotheses):
        hypothesis = memory.hypotheses[hypothesis_id]
        if {hypothesis.hypothesis_id, hypothesis.family_id} & rejected_ids:
            continue
        for lane in sorted(hypothesis.lanes):
            artifact = memory.research_artifact(hypothesis_id, lane=lane, as_of=as_of)
            if artifact is None:
                continue
            confidence = float(artifact["research_confidence"])
            events = artifact.get("evidence_events")
            if not isinstance(events, list) or not events:
                raise CausalMemoryError("supported artifact lacks structured evidence")
            downstream_fp = _fingerprint(artifact, lane)
            lane_name = "big-move-causal" if lane == "big_move" else "strategy-component-causal"
            evidence_depth = min(1.0, len(events) / 4.0)
            mission = build_mission(
                lane=lane_name,
                horizon=f"{hypothesis.horizon_hours}h",
                direction="RESEARCH_ONLY",
                theme=f"causal_{lane}_{downstream_fp.rsplit(':', 1)[-1][:12]}",
                hypothesis=(f"Independently test supported mechanism {hypothesis_id} with fresh chronological evidence; "
                            "do not reuse formation or confirmation observations."),
                expected_information_gain=min(0.95, 0.55 + 0.50 * max(0.0, confidence - 0.5) + 0.10 * evidence_depth),
                expected_signal_impact=0.20,
                expected_profitability_impact=min(0.45, 0.12 + 0.60 * max(0.0, confidence - 0.5)),
                sample_readiness=min(0.90, 0.55 + 0.20 * evidence_depth),
                novelty=0.80,
                falsification_value=0.95,
                actionable_evidence_probability=min(0.80, confidence),
                compute_cost=0.25,
                experiment_id=downstream_fp,
            )
            missions.append({
                **mission.to_dict(),
                "causal_repricing": {
                    "schema_version": SCHEMA_VERSION,
                    "evidence_level": "SUPPORTED_MECHANISM_RESEARCH_ONLY",
                    "source_hypothesis_id": hypothesis_id,
                    "source_hypothesis_fingerprint": artifact["hypothesis_fingerprint"],
                    "downstream_fingerprint": downstream_fp,
                    "research_confidence": confidence,
                    "formation_provenance_fingerprints": list(artifact["formation_provenance_fingerprints"]),
                    "evidence_event_ids": [str(event.get("event_id")) for event in events],
                    "matched_controls": list(artifact["frozen_test_contract"]["matched_controls"]),
                    "narrative_evidence_consumed": False,
                    "requires_fresh_chronological_validation": True,
                    "formation_or_confirmation_rows_reusable": False,
                    "lane_independence_required": True,
                },
                **SAFE,
            })
    missions.sort(
        key=lambda row: (-float(_finite_priority(row)), str(row["mission_id"]))
    )
    return missions


def _load() -> CausalRepricingMemory:
    import db
    if not db.configured():
        raise CausalMemoryError("durable causal memory is not configured")
    from money_intelligence_causal_supabase import SupabaseCausalMemory
    return SupabaseCausalMemory().load()


def causal_feedback(*, loader: Callable[[], CausalRepricingMemory] | None = None, as_of: str | None = None) -> dict[str, Any]:
    cutoff = as_of or _now()
    try:
        memory = (loader or _load)()
        if not isinstance(memory, CausalRepricingMemory):
            raise CausalMemoryError("invalid causal memory state")
        missions = build_supported_missions(memory, as_of=cutoff)
    except Exception:
        return {"status": "WAIT_CAUSAL_MEMORY_UNAVAILABLE", "as_of": cutoff, "missions": [], "mission_count": 0,
                "structured_evidence_consumed": False, "narrative_evidence_consumed": False, **SAFE}
    return {"status": "AVAILABLE" if missions else "AVAILABLE_NO_SUPPORTED_MECHANISMS", "as_of": cutoff,
            "missions": missions, "mission_count": len(missions), "structured_evidence_consumed": bool(missions),
            "narrative_evidence_consumed": False, **SAFE}


def apply_causal_feedback(state: dict[str, Any], *, loader: Callable[[], CausalRepricingMemory] | None = None,
                          as_of: str | None = None) -> dict[str, Any]:
    result = deepcopy(state)
    feedback = causal_feedback(loader=loader, as_of=as_of)
    result["money_intelligence_causal"] = feedback
    if feedback["status"] != "AVAILABLE":
        return result
    imported_missions = (
        result.get("missions") if isinstance(result.get("missions"), list) else []
    )
    missions = [row for row in imported_missions if _finite_priority(row) is not None]
    result["missions"] = missions
    known = {str(row.get("mission_id")) for row in missions if isinstance(row, dict)}
    causal_rows = [deepcopy(row) for row in feedback["missions"]]
    for row in causal_rows:
        if row["mission_id"] not in known:
            missions.append(row)
            known.add(row["mission_id"])
    missions.sort(
        key=lambda row: (-float(_finite_priority(row)), str(row.get("mission_id", "")))
    )
    imported_current = (
        result.get("next_missions")
        if isinstance(result.get("next_missions"), list)
        else []
    )
    current = [row for row in imported_current if _finite_priority(row) is not None]
    by_id = {str(row["mission_id"]): deepcopy(row) for row in [*current, *causal_rows]
             if isinstance(row, dict) and row.get("mission_id")}
    ranked = sorted(
        by_id.values(),
        key=lambda row: (-float(_finite_priority(row)), str(row.get("mission_id", ""))),
    )[:5]
    result["next_missions"] = ranked
    report = result.get("daily_lead_report")
    if isinstance(report, dict):
        report["highest_priority_next_missions"] = deepcopy(ranked)
        report["money_intelligence_causal"] = deepcopy(feedback)
    return result

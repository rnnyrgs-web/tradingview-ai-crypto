"""Fail-closed runtime bridge from durable causal memory to research missions.

Only frozen hypotheses that pass the causal memory's point-in-time,
multiple-testing, contradiction, and decay gates can become missions.  This
module grants research prioritisation only; it cannot open OOS or trading.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import db
from money_intelligence_causal_memory import CausalMemoryError
from money_intelligence_causal_supabase import SupabaseCausalMemory
from research_director import build_mission


REJECTED_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "orchestration/rejected_fingerprints.json"
)
_LANE_MAP = {"big_move": "big-move", "strategy_component": "strategy-component"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _base(status: str, *, as_of: str) -> dict[str, Any]:
    return {
        "status": status,
        "as_of": as_of,
        "content_digest": None,
        "missions": [],
        "rejected_hypothesis_ids": [],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "oos_opening_authority": False,
        "broker_connected": False,
    }


def _canonical_rejected() -> set[str]:
    try:
        payload = json.loads(REJECTED_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CausalMemoryError("canonical rejected memory is unavailable") from exc
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise CausalMemoryError("canonical rejected memory is invalid")
    rejected: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise CausalMemoryError("canonical rejected memory is invalid")
        fingerprint = entry.get("fingerprint_id")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise CausalMemoryError("canonical rejected memory is invalid")
        rejected.add(fingerprint.strip())
    return rejected


def _mission_row(memory, hypothesis, artifact: dict[str, object], lane: str, digest: str):
    confidence = float(artifact["research_confidence"])
    effective_fingerprint = str(artifact["hypothesis_fingerprint"])
    director_lane = _LANE_MAP[lane]
    mission = build_mission(
        lane=director_lane,
        horizon=f"{hypothesis.horizon_hours}h",
        direction="BUY" if hypothesis.direction == "positive" else "SELL",
        theme=f"causal-repricing:{effective_fingerprint}",
        hypothesis=f"replicate and try to falsify: {hypothesis.statement}",
        expected_information_gain=confidence,
        expected_signal_impact=confidence,
        # Causal confidence is not a profitability estimate. Keep economics
        # neutral until the strategy evaluator supplies after-cost evidence.
        expected_profitability_impact=0.5,
        sample_readiness=min(1.0, len(artifact["evidence_events"]) / 2.0),
        novelty=0.75,
        falsification_value=0.95,
        actionable_evidence_probability=confidence,
        compute_cost=0.35,
        experiment_id=effective_fingerprint,
    ).to_dict()
    events = artifact["evidence_events"]
    mission["causal_evidence"] = {
        "memory_content_digest": digest,
        "hypothesis_id": hypothesis.hypothesis_id,
        "design_fingerprint": artifact["design_fingerprint"],
        "effective_fingerprint": effective_fingerprint,
        "formation_provenance_fingerprints": artifact[
            "formation_provenance_fingerprints"
        ],
        "event_ids": [event["event_id"] for event in events],
        "event_fingerprints": [event["event_fingerprint"] for event in events],
        "research_confidence": confidence,
        "as_of": artifact["as_of"],
        "frozen_test_contract": artifact["frozen_test_contract"],
    }
    mission.update(
        {
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "oos_opening_authority": False,
        }
    )
    return mission


def causal_mission_feedback(
    *, as_of: str | None = None, store: SupabaseCausalMemory | None = None
) -> dict[str, Any]:
    """Load durable causal memory and return only scientifically eligible missions.

    Backend, integrity, or canonical-rejection failures return no missions and
    intentionally omit raw exception details.
    """

    cutoff = as_of or _now()
    if store is None and not db.configured():
        return _base("WAIT_MEMORY_NOT_CONFIGURED", as_of=cutoff)
    try:
        durable_store = store or SupabaseCausalMemory()
        memory = durable_store.load()
        canonical_rejected = _canonical_rejected()
        document = memory.to_document()
        digest = str(document["content_digest"])
        missions: list[dict[str, Any]] = []
        rejected_hypotheses: list[str] = []
        for hypothesis_id in sorted(memory.hypotheses):
            hypothesis = memory.hypotheses[hypothesis_id]
            design = hypothesis.fingerprint
            effective = memory.effective_fingerprint(hypothesis)
            if (
                hypothesis_id in canonical_rejected
                or design in canonical_rejected
                or effective in canonical_rejected
            ):
                rejected_hypotheses.append(hypothesis_id)
                continue
            for lane in sorted(hypothesis.lanes):
                artifact = memory.research_artifact(
                    hypothesis_id, lane=lane, as_of=cutoff
                )
                if artifact is not None:
                    missions.append(
                        _mission_row(memory, hypothesis, artifact, lane, digest)
                    )
        missions.sort(key=lambda row: (str(row["lane"]), str(row["mission_id"])))
        result = _base("READY", as_of=cutoff)
        result.update(
            {
                "content_digest": digest,
                "missions": missions,
                "rejected_hypothesis_ids": rejected_hypotheses,
            }
        )
        return result
    except (CausalMemoryError, OSError, TypeError, ValueError, KeyError):
        return _base("WAIT_MEMORY_UNAVAILABLE", as_of=cutoff)

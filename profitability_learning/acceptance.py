"""Idempotent runtime proof for the canonical rejected lead-lag experiment.

This module only replays an already-sealed development/validation result into
the configured durable learning memory.  It cannot open OOS data, promote a
strategy, connect a broker, or authorize trading.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
from threading import Lock

from btc_leadlag_selection import persist_selection
from research_artifact import verify_research_envelope

from .runtime import apply_queue_feedback, factory_feedback, learning_snapshot


ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz"
)
PAYLOAD_SHA256 = "9a73a00e6052783525b77ec36527bc5fb12c2891ebd300da00ff744fd3e4951c"
FINGERPRINT_ID = "DISC-BTC-LEADLAG-001-v1"
STRATEGY_FINGERPRINT = "e34357280eb06acc965b81aa8a4655d71c29010cd39f476e18d974e54d244e4e"
COMPONENT_FINGERPRINT = "91878bc73360ad02485b2f495c00bd2374ae81f72fb3d9404857b41d0a2c6ef0"
TRAINING_EXPERIMENT_ID = "0bc7d582a0730149242d700d848f5fb23c16c2fdea35944579587c1c813f2b97"
VALIDATION_EXPERIMENT_ID = "806f6bd58d69a3ad1d81c7191f06cf564be2dfbfc8697f889eff3038426ac696"
EXPECTED_EXPERIMENTS = {TRAINING_EXPERIMENT_ID, VALIDATION_EXPERIMENT_ID}

_lock = Lock()
_snapshot = {
    "status": "NOT_RUN",
    "research_only": True,
    "trade_authority": False,
    "promotion_authority": False,
    "broker_connected": False,
}


def _safe(status: str, **values) -> dict:
    return {
        "status": status,
        **values,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
    }


def _publish(result: dict) -> dict:
    global _snapshot
    with _lock:
        _snapshot = deepcopy(result)
    return deepcopy(result)


def acceptance_snapshot() -> dict:
    with _lock:
        return deepcopy(_snapshot)


def _load_selection(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        envelope = json.load(handle)
    if not verify_research_envelope(envelope):
        raise ValueError("invalid research envelope")
    if envelope.get("integrity", {}).get("payload_sha256") != PAYLOAD_SHA256:
        raise ValueError("unexpected research payload")
    payload = envelope["payload"]
    selection = payload["selection"]
    if (
        selection.get("fingerprint_id") != FINGERPRINT_ID
        or selection.get("screen_status") != "PRE_OOS_FAIL"
        or selection.get("economic_pre_oos_pass") is not False
        or selection.get("untouched_oos_opened") is not False
        or selection.get("genuine_forward_opened") is not False
        or payload.get("untouched_oos_opened") is not False
        or payload.get("genuine_forward_opened") is not False
        or payload.get("trade_authority") is not False
        or payload.get("promotion_authority") is not False
    ):
        raise ValueError("canonical rejection safety boundary mismatch")
    contracts = selection["rich_primary_max_stress"]
    for split in ("training", "validation"):
        contract = contracts[split]["experiment"]["contract"]
        if contract.get("strategy_fingerprint") != STRATEGY_FINGERPRINT:
            raise ValueError("canonical strategy identity mismatch")
    return selection


def _target_ids(memory: dict) -> set[str]:
    return {
        row.get("experiment_id")
        for row in memory.get("experiments", [])
        if row.get("experiment_id") in EXPECTED_EXPERIMENTS
    }


def run_canonical_acceptance(artifact_path: str | Path = ARTIFACT_PATH) -> dict:
    """Replay and verify the sealed negative result against durable memory."""
    try:
        selection = _load_selection(Path(artifact_path))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return _publish(_safe(
            "WAIT_INVALID_ARTIFACT",
            required_action="Restore the exact sealed canonical acceptance artifact",
        ))

    try:
        before_state = learning_snapshot()
        before = before_state.get("memory")
        if before_state.get("status") != "AVAILABLE" or not isinstance(before, dict):
            raise RuntimeError("durable memory unavailable")
        before_ids = _target_ids(before)

        persisted = persist_selection(selection)
        after_state = learning_snapshot()
        after = after_state.get("memory")
        if after_state.get("status") != "AVAILABLE" or not isinstance(after, dict):
            raise RuntimeError("durable memory unavailable after completion")
        after_ids = _target_ids(after)

        # A second real write attempt is the restart/replay proof.  Both storage
        # backends enforce immutable experiment identity and suppress duplicates.
        persist_selection(selection)
        replay_state = learning_snapshot()
        replay = replay_state.get("memory")
        if replay_state.get("status") != "AVAILABLE" or not isinstance(replay, dict):
            raise RuntimeError("durable memory unavailable after replay")
        replay_ids = _target_ids(replay)

        completion_ids = {
            persisted["training"].get("experiment_id"),
            persisted["validation"].get("experiment_id"),
        }
        duplicate_suppressed = (
            after_ids == replay_ids == EXPECTED_EXPERIMENTS
            and len(after.get("experiments", [])) == len(replay.get("experiments", []))
        )
        if completion_ids != EXPECTED_EXPERIMENTS or not duplicate_suppressed:
            raise RuntimeError("completion identity or replay invariant failed")

        candidate = {
            "experiment_id": "canonical-rejection-admission-probe",
            "family": "cross-asset delayed price discovery",
            "strategy_fingerprint": STRATEGY_FINGERPRINT,
            "information_priority": 1.0,
        }
        admitted = apply_queue_feedback({"experiments": [candidate]})["experiments"][0]
        feedback = admitted["learning_feedback"]
        missions = factory_feedback().get("missions", [])
        learning_mission = next(
            (
                mission
                for mission in missions
                if mission.get("source_experiment_id") == TRAINING_EXPERIMENT_ID
                and mission.get("mode") == "LEARN"
            ),
            None,
        )
        component = replay.get("components", {}).get(COMPONENT_FINGERPRINT, {})
        if (
            feedback.get("factor") != 0.0
            or feedback.get("reason") != "rejected_exact_fingerprint"
            or component.get("evidence_level") != "DEVELOPMENT_ASSOCIATION"
            or learning_mission is None
        ):
            raise RuntimeError("learning consumption invariant failed")

        return _publish(_safe(
            "PASSED",
            fingerprint_id=FINGERPRINT_ID,
            persistence={
                "experiment_count": len(after_ids),
                "new_experiment_count": len(after_ids - before_ids),
                "replay_experiment_count": len(replay_ids),
                "duplicate_suppressed": duplicate_suppressed,
                "training_experiment_id": TRAINING_EXPERIMENT_ID,
                "validation_experiment_id": VALIDATION_EXPERIMENT_ID,
            },
            admission={
                "exact_rejected_fingerprint_veto": True,
                "learning_factor": feedback["factor"],
                "reason": feedback["reason"],
            },
            learning={
                "component_kind": "underreaction",
                "component_evidence_level": component["evidence_level"],
                "component_proven": False,
                "learning_mission_generated": True,
                "learning_mission_mode": learning_mission["mode"],
            },
        ))
    except Exception:
        # Startup remains research-only and exposes an actionable, non-sensitive
        # wait state.  Configured memory is never reset or replaced on failure.
        return _publish(_safe(
            "WAIT_MEMORY_UNAVAILABLE",
            required_action="Restore durable profitability memory and replay canonical acceptance",
        ))

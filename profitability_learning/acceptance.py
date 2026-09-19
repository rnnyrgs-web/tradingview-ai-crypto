"""Bounded deployed-runtime acceptance for one already-opened rejected artifact.

This module does not evaluate a strategy or accept caller-supplied research.  It
replays the canonical sealed pre-OOS failure through the same durable completion
and admission paths used by autonomous research workers.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

from btc_leadlag_selection import (
    FROZEN_CONTRACT_SHA256,
    FROZEN_DATASET_SHA256,
    persist_selection,
)
from profitability_learning.contracts import SAFE, fingerprint
from profitability_learning.runtime import (
    apply_queue_feedback,
    factory_feedback,
    learning_snapshot,
)
from research_artifact import verify_research_envelope
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz"
EXPECTED_FINGERPRINT = "DISC-BTC-LEADLAG-001-v1"
EXPECTED_ARTIFACT_PAYLOAD_SHA256 = "9a73a00e6052783525b77ec36527bc5fb12c2891ebd300da00ff744fd3e4951c"
MAX_ARTIFACT_BYTES = 3_000_000


def _deployed_sha(required: bool) -> str | None:
    value = os.getenv("RENDER_GIT_COMMIT", "").strip().lower()
    valid = len(value) == 40 and all(char in "0123456789abcdef" for char in value)
    if required and not valid:
        raise ValueError("valid deployed SHA is required for runtime acceptance")
    return value if valid else None


def _read_bounded_gzip_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("canonical acceptance artifact is missing or oversized")
    with gzip.open(path, "rb") as handle:
        raw = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("canonical acceptance artifact expands beyond its bound")
    try:
        envelope = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical acceptance artifact is malformed") from exc
    if not isinstance(envelope, dict) or not verify_research_envelope(envelope):
        raise ValueError("canonical acceptance artifact integrity mismatch")
    if (envelope.get("schema_version") != 2
            or envelope.get("integrity", {}).get("payload_sha256") != EXPECTED_ARTIFACT_PAYLOAD_SHA256):
        raise ValueError("canonical acceptance artifact fingerprint mismatch")
    return envelope


def _validated_selection(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    envelope = _read_bounded_gzip_json(path)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("canonical acceptance payload is missing")
    selection = payload.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("canonical acceptance selection is missing")
    if selection.get("fingerprint_id") != EXPECTED_FINGERPRINT:
        raise ValueError("canonical acceptance fingerprint mismatch")
    if payload.get("contract_sha256") != FROZEN_CONTRACT_SHA256:
        raise ValueError("canonical acceptance contract fingerprint mismatch")
    manifest = payload.get("dataset_manifest")
    if not isinstance(manifest, dict) or manifest.get("normalized_rows_sha256") != FROZEN_DATASET_SHA256:
        raise ValueError("canonical acceptance dataset fingerprint mismatch")
    required = {
        "candidate_returns_inspected": True,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    if any(payload.get(key) is not expected for key, expected in required.items()):
        raise ValueError("canonical acceptance evidence boundary mismatch")
    selection_required = {
        "screen_status": "PRE_OOS_FAIL",
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_execution_authority": False,
        "broker_connected": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
    }
    if (selection.get("economic_pre_oos_pass") is not False
            or any(selection.get(key) != expected for key, expected in selection_required.items())):
        raise ValueError("canonical acceptance rejected pre-OOS state mismatch")
    return envelope, selection


def _admission_probe(selection: dict[str, Any]) -> dict[str, Any]:
    training = selection["rich_primary_max_stress"]["training"]["experiment"]
    return {
        "experiment_id": "runtime-acceptance-exact-rejected-fingerprint",
        "family": training["contract"]["family"],
        "strategy_fingerprint": training["contract"]["strategy_fingerprint"],
        "information_priority": 100.0,
        "source_samples": 20,
        "source_independent_samples": 20,
        "dimension": "runtime_acceptance",
        "group": "sealed_rejected_artifact",
        "hypothesis": "An exact rejected fingerprint must remain ineligible after durable replay.",
        "predicted_mechanism": "Rejected-fingerprint memory must veto duplicate heavy research.",
        "target_horizon": "both",
        "expected_signal_quality_effect": "No signal claim; verify rejection consumption only.",
        "evidence_needed": ["durable completion", "exact-fingerprint admission veto"],
        "falsification_criteria": ["the exact rejected fingerprint is admitted"],
        "chronological_oos_requirements": ["untouched OOS remains unopened"],
        "realistic_cost_treatment": ["consume the sealed 3x-cost completion"],
        "independent_sample_requirements": ["use only the canonical completed experiment"],
        "priority_factors": {
            "expected_incremental_after_cost_profitability_impact": 1.0,
            "expected_genuine_signal_quality_impact": 1.0,
            "expected_information_falsification_value": 1.0,
            "probability_actionable_evidence": 1.0,
            "compute_api_cost_units": 0.25,
        },
        "compute_class": "heavy_candidate",
        "status": "QUEUED_RESEARCH_ONLY",
        "required_validation": ["untouched_oos", "realistic_cost_stress", "genuine_forward_shadow"],
        "result": None,
        "evidence_conclusion": "unresolved",
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }


def _experiment_count(snapshot: dict[str, Any]) -> int:
    memory = snapshot.get("memory")
    return len(memory.get("experiments", [])) if isinstance(memory, dict) else 0


def run_rejected_leadlag_acceptance(
    *, artifact_path: Path = ARTIFACT_PATH, require_deployed_sha: bool = True
) -> dict[str, Any]:
    """Replay and attest the exact sealed failure through live durable paths."""
    deployed_sha = _deployed_sha(require_deployed_sha)
    envelope, selection = _validated_selection(Path(artifact_path))
    before = learning_snapshot()
    if before.get("status") != "AVAILABLE":
        raise ValueError("durable profitability memory is unavailable")

    first = persist_selection(selection)
    after_first = learning_snapshot()
    first_state_digest = fingerprint(after_first["memory"])
    replay = persist_selection(selection)
    after_replay = learning_snapshot()
    replay_state_digest = fingerprint(after_replay["memory"])

    training = first["training"]
    validation = first["validation"]
    if training.get("persistence_status") != "PERSISTED" or validation.get("persistence_status") != "PERSISTED":
        raise ValueError("canonical acceptance completion did not persist")
    if replay["training"].get("input_digest") != training.get("input_digest"):
        raise ValueError("canonical acceptance training replay changed identity")
    if replay["validation"].get("input_digest") != validation.get("input_digest"):
        raise ValueError("canonical acceptance validation replay changed identity")
    if first_state_digest != replay_state_digest:
        raise ValueError("canonical acceptance replay was not idempotent")

    candidate = _admission_probe(selection)
    queue = apply_queue_feedback({"experiments": [candidate], "experiment_count": 1})
    feedback = queue["experiments"][0]["learning_feedback"]
    dispatch = build_heavy_dispatch_plan(queue)
    factory = factory_feedback()
    memory = after_replay["memory"]
    strategy_fingerprint = training["contract"]["strategy_fingerprint"]
    component_observations = sum(
        1
        for component in memory.get("components", {}).values()
        for observation in component.get("observations", [])
        if observation.get("effect") is not None
        and observation.get("experiment_id") == training["experiment_id"]
    )
    interaction_observations = sum(
        1
        for observations in memory.get("interactions", {}).values()
        for observation in observations
        if observation.get("experiment_id") == training["experiment_id"]
    )
    mission_ids = [mission["id"] for mission in factory.get("missions", [])]
    if training.get("outcome") != "LEARN_AND_PIVOT" or validation.get("outcome") != "LEARN_AND_PIVOT":
        raise ValueError("canonical rejected completion classification changed")
    if (strategy_fingerprint not in memory.get("rejected_fingerprints", [])
            or feedback.get("reason") != "rejected_exact_fingerprint"
            or feedback.get("changes_eligibility") is not True
            or dispatch.get("selected_count") != 0):
        raise ValueError("durable rejected-fingerprint admission veto failed")
    if (factory.get("status") != "AVAILABLE"
            or component_observations < 1
            or not mission_ids):
        raise ValueError("durable component or mission learning was not consumed")

    return {
        "ok": True,
        "schema_version": 1,
        "deployed_sha": deployed_sha,
        "fingerprint_id": EXPECTED_FINGERPRINT,
        "artifact_payload_sha256": envelope["integrity"]["payload_sha256"],
        "screen_status": selection["screen_status"],
        "completion": {
            "training": {
                key: training[key]
                for key in ("experiment_id", "input_digest", "outcome", "persistence_status")
            },
            "validation": {
                key: validation[key]
                for key in ("experiment_id", "input_digest", "outcome", "persistence_status")
            },
        },
        "persistence": {
            "before_experiment_count": _experiment_count(before),
            "after_first_experiment_count": _experiment_count(after_first),
            "after_replay_experiment_count": _experiment_count(after_replay),
            "state_digest_after_first": first_state_digest,
            "state_digest_after_replay": replay_state_digest,
            "replay_idempotent": first_state_digest == replay_state_digest,
        },
        "learning_consumption": {
            "strategy_fingerprint": strategy_fingerprint,
            "rejected_exact_fingerprint": strategy_fingerprint in memory.get("rejected_fingerprints", []),
            "queue_feedback_reason": feedback["reason"],
            "queue_feedback_changes_eligibility": feedback["changes_eligibility"],
            "heavy_dispatch_selected_count": dispatch["selected_count"],
            "component_observation_count": component_observations,
            "interaction_observation_count": interaction_observations,
            "mission_ids": mission_ids,
        },
        "evidence_boundaries": {
            "candidate_returns_already_inspected": True,
            "untouched_oos_opened": False,
            "genuine_forward_opened": False,
        },
        "safety": dict(SAFE),
    }

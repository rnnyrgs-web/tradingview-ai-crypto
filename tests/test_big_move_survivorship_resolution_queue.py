from __future__ import annotations

import copy
import hashlib
import json

import pytest

from big_move_survivorship_metadata import build_survivorship_enumeration_manifest
from big_move_survivorship_resolution_queue import (
    SurvivorshipResolutionQueueError,
    build_identity_resolution_queue,
    reject_survivorship_enumeration_as_membership_lineage,
    validate_provider_native_membership_provenance,
)


def _payload(*, active_old=False, old_available_to="2022-06-01T00:00:00.000Z") -> dict:
    return {
        "id": "binance",
        "datasets": {
            "symbols": [
                {
                    "id": "OLDUSDT",
                    "availableSince": "2021-01-01T00:00:00.000Z",
                    "availableTo": old_available_to,
                    "dataTypes": ["trades", "incremental_book_L2"],
                    "active": active_old,
                },
                {
                    "id": "LIVEUSDT",
                    "availableSince": "2021-02-01T00:00:00.000Z",
                    "dataTypes": ["trades", "quotes"],
                    "active": True,
                },
            ]
        },
    }


def _manifest(payload=None) -> dict:
    payload = _payload() if payload is None else payload
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return build_survivorship_enumeration_manifest(
        raw,
        expected_source_response_sha256=hashlib.sha256(raw).hexdigest(),
        captured_at="2026-09-23T19:00:00Z",
    )


def test_inactive_dead_identity_is_retained_only_as_unresolved_work() -> None:
    queue = build_identity_resolution_queue(_manifest())
    assert [item["venue_symbol"] for item in queue["work_items"]] == ["LIVEUSDT", "OLDUSDT"]
    old = queue["work_items"][1]
    assert old["identity_resolution_state"] == "UNRESOLVED_EXTERNAL_PIT_EVIDENCE_REQUIRED"
    assert old["allowed_downstream_consumer"] == "IDENTITY_RESOLUTION_WORK_QUEUE_ONLY"
    assert old["provider_collection_available_to"] == "2022-06-01T00:00:00Z"
    assert old["provider_collection_bounds_authority"] == "NONE"
    assert old["historical_membership_authority"] == "NONE"
    assert old["delisting_time_authority"] == "NONE"
    assert old["negative_control_authority"] == "NONE"
    assert old["label_authority"] == "NONE"
    assert old["cohort_snapshot_authority"] is False


def test_current_active_change_cannot_change_queue_authority() -> None:
    first = build_identity_resolution_queue(_manifest(_payload(active_old=False)))
    second = build_identity_resolution_queue(_manifest(_payload(active_old=True)))
    for queue in (first, second):
        old = next(item for item in queue["work_items"] if item["venue_symbol"] == "OLDUSDT")
        assert old["identity_resolution_state"] == "UNRESOLVED_EXTERNAL_PIT_EVIDENCE_REQUIRED"
        assert old["historical_membership_authority"] == "NONE"
        assert old["negative_control_authority"] == "NONE"
        assert old["cohort_snapshot_authority"] is False


def test_available_to_change_never_creates_delisting_or_negative_control_authority() -> None:
    stopped = build_identity_resolution_queue(_manifest(_payload(old_available_to="2022-06-01T00:00:00.000Z")))
    later = build_identity_resolution_queue(_manifest(_payload(old_available_to="2024-01-01T00:00:00.000Z")))
    for queue in (stopped, later):
        old = next(item for item in queue["work_items"] if item["venue_symbol"] == "OLDUSDT")
        assert old["delisting_time_authority"] == "NONE"
        assert old["negative_control_authority"] == "NONE"
        assert old["historical_membership_authority"] == "NONE"


def test_manifest_and_source_fingerprint_substitution_fail_closed() -> None:
    manifest = _manifest()
    tampered = copy.deepcopy(manifest)
    tampered["source_response_sha256"] = "0" * 64
    with pytest.raises(SurvivorshipResolutionQueueError, match="manifest fingerprint mismatch"):
        build_identity_resolution_queue(tampered)

    tampered = copy.deepcopy(manifest)
    tampered["manifest_fingerprint"] = "0" * 64
    with pytest.raises(SurvivorshipResolutionQueueError, match="manifest fingerprint mismatch"):
        build_identity_resolution_queue(tampered)


def test_enumeration_and_queue_lineage_are_forbidden_as_membership_evidence() -> None:
    manifest = _manifest()
    queue = build_identity_resolution_queue(manifest)
    for forbidden in (manifest, queue, queue["work_items"][0]):
        with pytest.raises(SurvivorshipResolutionQueueError, match="forbidden in membership lineage"):
            reject_survivorship_enumeration_as_membership_lineage(forbidden)


def test_membership_provenance_is_required_and_cannot_launder_enumeration() -> None:
    proof_sha = "1" * 64
    with pytest.raises(SurvivorshipResolutionQueueError, match="membership provenance is required"):
        validate_provider_native_membership_provenance(
            None,
            venue_symbol="OLDUSDT",
            decision_at="2021-02-01T00:00:00Z",
            source_proof_sha256=proof_sha,
        )

    provenance = {
        "schema": "binance_market_presence_provenance.v1",
        "source_kind": "BINANCE_PROVIDER_NATIVE_PIT_MARKET_PRESENCE",
        "venue": "BINANCE_SPOT",
        "venue_symbol": "OLDUSDT",
        "decision_at": "2021-02-01T00:00:00Z",
        "source_proof_sha256": proof_sha,
        "enumeration_used_as_membership_evidence": False,
    }
    validate_provider_native_membership_provenance(
        provenance,
        venue_symbol="OLDUSDT",
        decision_at="2021-02-01T00:00:00Z",
        source_proof_sha256=proof_sha,
    )

    wrong = dict(provenance)
    wrong["source_proof_sha256"] = "2" * 64
    with pytest.raises(SurvivorshipResolutionQueueError, match="source-proof binding mismatch"):
        validate_provider_native_membership_provenance(
            wrong,
            venue_symbol="OLDUSDT",
            decision_at="2021-02-01T00:00:00Z",
            source_proof_sha256=proof_sha,
        )

    laundered = dict(provenance)
    laundered["enumeration_manifest_fingerprint"] = _manifest()["manifest_fingerprint"]
    with pytest.raises(SurvivorshipResolutionQueueError, match="forbidden in membership lineage"):
        validate_provider_native_membership_provenance(
            laundered,
            venue_symbol="OLDUSDT",
            decision_at="2021-02-01T00:00:00Z",
            source_proof_sha256=proof_sha,
        )

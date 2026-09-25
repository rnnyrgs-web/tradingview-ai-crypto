from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

import pytest

from big_move_cohort_preflight import _validate_membership_derivation


DECISION_AT = "2021-02-01T00:00:00Z"
DECISION_DT = datetime(2021, 2, 1, tzinfo=timezone.utc)
SOURCE_PROOF_SHA = "1" * 64


def _provenance(*, venue_symbol: str = "TESTUSDT", source_proof_sha256: str = SOURCE_PROOF_SHA) -> dict:
    return {
        "schema": "binance_market_presence_provenance.v1",
        "source_kind": "BINANCE_PROVIDER_NATIVE_PIT_MARKET_PRESENCE",
        "venue": "BINANCE_SPOT",
        "venue_symbol": venue_symbol,
        "decision_at": DECISION_AT,
        "source_proof_sha256": source_proof_sha256,
        "enumeration_used_as_membership_evidence": False,
    }


def _presence(*, include_provenance: bool = True, venue_symbol: str = "TESTUSDT") -> dict:
    value = {
        "schema": "binance_market_presence.v1",
        "venue": "BINANCE_SPOT",
        "venue_symbol": venue_symbol,
        "decision_at": DECISION_AT,
        "member": True,
        "tradable": True,
        "source_proof": {
            "artifact_relpath": "provider-native-market-presence-proof.json",
            "sha256": SOURCE_PROOF_SHA,
        },
    }
    if include_provenance:
        value["membership_provenance"] = _provenance(venue_symbol=venue_symbol)
    return value


def _record(tmp_path, presence: dict, *, value: bool = True) -> dict:
    raw = json.dumps(presence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = tmp_path / "presence.json"
    path.write_bytes(raw)
    return {
        "value": value,
        "derivation": {
            "transform_id": "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
            "transform_version": "1",
            "parameters": {"rule": "verified_market_presence_at_decision"},
            "inputs": [
                {
                    "artifact_relpath": "presence.json",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            ],
        },
    }


def test_membership_boundary_requires_provider_native_provenance(tmp_path) -> None:
    record = _record(tmp_path, _presence(include_provenance=False))
    with pytest.raises(ValueError, match="membership provenance is required"):
        _validate_membership_derivation(record, tmp_path, DECISION_DT, field="member")


def test_membership_boundary_rejects_direct_survivorship_enumeration_material(tmp_path) -> None:
    presence = _presence()
    presence["enumeration_manifest_fingerprint"] = "2" * 64
    record = _record(tmp_path, presence)
    with pytest.raises(ValueError, match="survivorship enumeration"):
        _validate_membership_derivation(record, tmp_path, DECISION_DT, field="member")


def test_membership_boundary_rejects_queue_rewrapping(tmp_path) -> None:
    presence = _presence()
    presence["lineage"] = {
        "schema_version": "2X-SURVIVORSHIP-IDENTITY-RESOLUTION-QUEUE-MANIFEST-001-v1",
        "allowed_downstream_consumer": "IDENTITY_RESOLUTION_WORK_QUEUE_ONLY",
    }
    record = _record(tmp_path, presence)
    with pytest.raises(ValueError, match="survivorship enumeration"):
        _validate_membership_derivation(record, tmp_path, DECISION_DT, field="member")


def test_membership_boundary_rejects_source_proof_fingerprint_substitution(tmp_path) -> None:
    presence = _presence()
    presence["membership_provenance"] = _provenance(source_proof_sha256="3" * 64)
    record = _record(tmp_path, presence)
    with pytest.raises(ValueError, match="source-proof binding mismatch"):
        _validate_membership_derivation(record, tmp_path, DECISION_DT, field="member")


def test_membership_boundary_binds_provider_native_provenance_to_enclosing_symbol(tmp_path) -> None:
    record = _record(tmp_path, _presence(venue_symbol="TESTUSDT"))
    with pytest.raises(ValueError, match="subject mismatch"):
        _validate_membership_derivation(
            record,
            tmp_path,
            DECISION_DT,
            field="member",
            venue_symbol="OTHERUSDT",
        )


def test_membership_boundary_accepts_separately_authenticated_provider_native_lineage_shape(tmp_path) -> None:
    record = _record(tmp_path, _presence(venue_symbol="TESTUSDT"))
    _validate_membership_derivation(
        record,
        tmp_path,
        DECISION_DT,
        field="member",
        venue_symbol="TESTUSDT",
    )

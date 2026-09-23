from __future__ import annotations

import copy
import hashlib
import json

import pytest

from big_move_survivorship_metadata import (
    CONTRACT_ID,
    SurvivorshipMetadataError,
    build_survivorship_enumeration_manifest,
)


def _payload() -> dict:
    return {
        "id": "binance",
        "datasets": {
            "symbols": [
                {
                    "id": "OLDUSDT",
                    "availableSince": "2021-01-01T00:00:00.000Z",
                    "availableTo": "2022-06-01T00:00:00.000Z",
                    "dataTypes": ["trades", "incremental_book_L2"],
                    "active": False,
                },
                {
                    "id": "LIVEUSDT",
                    "availableSince": "2021-02-01T00:00:00.000Z",
                    "dataTypes": ["trades", "quotes"],
                    "active": True,
                },
                {
                    "id": "BTCBUSD",
                    "availableSince": "2021-02-01T00:00:00.000Z",
                    "dataTypes": ["trades"],
                },
                {
                    "id": "SPOT",
                    "availableSince": "2021-02-01T00:00:00.000Z",
                    "dataTypes": ["trades"],
                },
            ]
        },
    }


def _raw(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _manifest(payload: dict | None = None) -> dict:
    chosen = _payload() if payload is None else payload
    raw = _raw(chosen)
    return build_survivorship_enumeration_manifest(
        raw,
        expected_source_response_sha256=hashlib.sha256(raw).hexdigest(),
        captured_at="2026-09-23T02:00:00Z",
    )


def test_inactive_dead_symbol_is_retained_for_identity_enumeration() -> None:
    manifest = _manifest()
    assert manifest["contract_id"] == CONTRACT_ID
    assert manifest["source_response_bytes_verified"] is True
    assert [row["symbol"] for row in manifest["symbols"]] == ["LIVEUSDT", "OLDUSDT"]
    old = manifest["symbols"][1]
    assert old["provider_collection_available_to"] == "2022-06-01T00:00:00Z"
    assert old["historical_membership_state"] == "UNRESOLVED"
    assert old["delisting_state"] == "CENSORED_DELISTING_TIME_UNKNOWN"
    assert old["available_to_is_delisting_time"] is False


def test_current_active_field_is_never_consumed_for_historical_membership() -> None:
    first = _manifest()
    changed = _payload()
    changed["datasets"]["symbols"][0]["active"] = True
    changed["datasets"]["symbols"][1]["active"] = False
    second = _manifest(changed)
    assert first["symbols"] == second["symbols"]
    assert first["enumeration_semantic_fingerprint"] == second["enumeration_semantic_fingerprint"]
    assert first["manifest_fingerprint"] != second["manifest_fingerprint"]
    assert all(row["current_active_field_consumed"] is False for row in first["symbols"])


def test_available_to_never_grants_delisting_or_negative_control_authority() -> None:
    manifest = _manifest()
    assert manifest["delisting_time_authority"] == "NONE"
    assert manifest["negative_control_authority"] == "NONE"
    assert manifest["historical_membership_authority"] == "NONE"
    assert manifest["label_authority"] == "NONE"
    assert manifest["model_authority"] == "NONE"
    assert manifest["candidate_authority"] == "NONE"
    assert manifest["broker_trading_authority"] == "NONE"


def test_duplicate_or_reused_symbol_id_fails_closed() -> None:
    payload = _payload()
    duplicate = copy.deepcopy(payload["datasets"]["symbols"][0])
    duplicate["availableSince"] = "2023-01-01T00:00:00.000Z"
    duplicate["availableTo"] = None
    payload["datasets"]["symbols"].append(duplicate)
    with pytest.raises(SurvivorshipMetadataError, match="duplicate/reused symbol id OLDUSDT"):
        _manifest(payload)


def test_semantic_fingerprint_is_permutation_stable_but_manifest_binds_raw_bytes() -> None:
    one = _manifest()
    payload = _payload()
    payload["datasets"]["symbols"] = list(reversed(payload["datasets"]["symbols"]))
    two = _manifest(payload)
    assert one["symbols"] == two["symbols"]
    assert one["enumeration_semantic_fingerprint"] == two["enumeration_semantic_fingerprint"]
    assert one["source_response_sha256"] != two["source_response_sha256"]
    assert one["manifest_fingerprint"] != two["manifest_fingerprint"]


def test_collection_interval_must_be_positive() -> None:
    payload = _payload()
    payload["datasets"]["symbols"][0]["availableTo"] = "2020-01-01T00:00:00Z"
    with pytest.raises(SurvivorshipMetadataError, match="non-positive collection interval"):
        _manifest(payload)


def test_wrong_exchange_and_bad_source_digest_fail_closed() -> None:
    payload = _payload()
    payload["id"] = "okex"
    with pytest.raises(SurvivorshipMetadataError, match="provider payload id must be binance"):
        _manifest(payload)

    raw = _raw(_payload())
    with pytest.raises(SurvivorshipMetadataError, match="lowercase SHA-256"):
        build_survivorship_enumeration_manifest(
            raw,
            expected_source_response_sha256="not-a-digest",
            captured_at="2026-09-23T02:00:00Z",
        )


def test_claimed_digest_cannot_authenticate_different_provider_bytes() -> None:
    original = _raw(_payload())
    changed = _payload()
    changed["datasets"]["symbols"][0]["availableSince"] = "2024-01-01T00:00:00.000Z"
    changed_raw = _raw(changed)
    with pytest.raises(SurvivorshipMetadataError, match="do not match expected SHA-256"):
        build_survivorship_enumeration_manifest(
            changed_raw,
            expected_source_response_sha256=hashlib.sha256(original).hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )


def test_provider_bytes_must_be_exact_valid_json_object() -> None:
    with pytest.raises(SurvivorshipMetadataError, match="non-empty exact retained bytes"):
        build_survivorship_enumeration_manifest(
            b"",
            expected_source_response_sha256=hashlib.sha256(b"").hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )

    invalid = b"{not-json"
    with pytest.raises(SurvivorshipMetadataError, match="contain valid JSON"):
        build_survivorship_enumeration_manifest(
            invalid,
            expected_source_response_sha256=hashlib.sha256(invalid).hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )

    array_payload = b"[]"
    with pytest.raises(SurvivorshipMetadataError, match="JSON must be an object"):
        build_survivorship_enumeration_manifest(
            array_payload,
            expected_source_response_sha256=hashlib.sha256(array_payload).hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )

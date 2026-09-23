from __future__ import annotations

import copy
import hashlib
import json

import pytest

from big_move_survivorship_metadata import (
    CONTRACT_ID,
    ONLY_ALLOWED_DOWNSTREAM_CONSUMER,
    QUEUE_CONTRACT_ID,
    SurvivorshipMetadataError,
    build_identity_resolution_work_queue,
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


def _queue(payload: dict | None = None) -> dict:
    return build_identity_resolution_work_queue(_manifest(payload))


def test_inactive_dead_symbol_is_retained_for_identity_enumeration() -> None:
    manifest = _manifest()
    assert manifest["contract_id"] == CONTRACT_ID
    assert manifest["source_response_bytes_verified"] is True
    assert manifest["capture_time_authority"] == "CALLER_DECLARED_NONE"
    assert manifest["capture_time_is_historical_availability_proof"] is False
    assert manifest["cohort_snapshot_authority"] is False
    assert manifest["only_allowed_downstream_consumer"] == ONLY_ALLOWED_DOWNSTREAM_CONSUMER
    assert [row["symbol"] for row in manifest["symbols"]] == ["LIVEUSDT", "OLDUSDT"]
    old = manifest["symbols"][1]
    assert old["provider_collection_available_to"] == "2022-06-01T00:00:00Z"
    assert old["historical_membership_state"] == "UNRESOLVED"
    assert old["delisting_state"] == "CENSORED_DELISTING_TIME_UNKNOWN"
    assert old["available_to_is_delisting_time"] is False
    assert old["cohort_snapshot_authority"] is False


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
    assert manifest["cohort_snapshot_authority"] is False
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


def test_duplicate_json_object_keys_fail_closed_before_semantic_use() -> None:
    raw = (
        b'{"id":"binance","datasets":{"symbols":[]},'
        b'"datasets":{"symbols":[{"id":"OLDUSDT","availableSince":"2021-01-01T00:00:00Z",'
        b'"dataTypes":["trades"]}]}}'
    )
    with pytest.raises(SurvivorshipMetadataError, match="duplicate object key 'datasets'"):
        build_survivorship_enumeration_manifest(
            raw,
            expected_source_response_sha256=hashlib.sha256(raw).hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )


def test_nonstandard_json_numeric_constants_fail_closed() -> None:
    raw = (
        b'{"id":"binance","datasets":{"symbols":[]},'
        b'"providerDiagnostic":NaN}'
    )
    with pytest.raises(SurvivorshipMetadataError, match="non-standard numeric constant NaN"):
        build_survivorship_enumeration_manifest(
            raw,
            expected_source_response_sha256=hashlib.sha256(raw).hexdigest(),
            captured_at="2026-09-23T02:00:00Z",
        )


def test_only_downstream_product_is_unresolved_identity_resolution_queue() -> None:
    manifest = _manifest()
    queue = build_identity_resolution_work_queue(manifest)
    assert queue["contract_id"] == QUEUE_CONTRACT_ID
    assert queue["source_enumeration_manifest_fingerprint"] == manifest["manifest_fingerprint"]
    assert queue["source_response_sha256"] == manifest["source_response_sha256"]
    assert queue["consumer_authority"] == "IDENTITY_RESOLUTION_WORK_QUEUE_ONLY"
    assert queue["historical_membership_authority"] == "NONE"
    assert queue["negative_control_authority"] == "NONE"
    assert queue["label_authority"] == "NONE"
    assert queue["cohort_snapshot_authority"] is False
    assert [item["venue_symbol"] for item in queue["work_items"]] == ["LIVEUSDT", "OLDUSDT"]
    for item in queue["work_items"]:
        assert item["enumeration_manifest_fingerprint"] == manifest["manifest_fingerprint"]
        assert item["source_response_sha256"] == manifest["source_response_sha256"]
        assert item["identity_resolution_state"] == "UNRESOLVED_TIMESTAMP_SAFE_MARKET_PRESENCE_REQUIRED"
        assert item["provider_collection_bounds_authority"] == "SEARCH_HINT_ONLY"
        assert item["historical_membership_authority"] == "NONE"
        assert item["delisting_time_authority"] == "NONE"
        assert item["negative_control_authority"] == "NONE"
        assert item["label_authority"] == "NONE"
        assert item["cohort_snapshot_authority"] is False
        assert item["required_next_proof"] == "SEPARATE_TIMESTAMP_SAFE_PIT_MARKET_PRESENCE_PROOF"


def test_active_state_cannot_change_queue_scientific_authority() -> None:
    first = _queue()
    payload = _payload()
    payload["datasets"]["symbols"][0]["active"] = True
    payload["datasets"]["symbols"][1]["active"] = False
    second = _queue(payload)
    assert [item["venue_symbol"] for item in first["work_items"]] == [item["venue_symbol"] for item in second["work_items"]]
    for queue in (first, second):
        assert queue["historical_membership_authority"] == "NONE"
        assert queue["negative_control_authority"] == "NONE"
        assert queue["cohort_snapshot_authority"] is False
        assert all(item["historical_membership_authority"] == "NONE" for item in queue["work_items"])
        assert all(item["cohort_snapshot_authority"] is False for item in queue["work_items"])


def test_available_to_can_only_change_search_hint_not_delisting_authority() -> None:
    first = _queue()
    payload = _payload()
    payload["datasets"]["symbols"][0]["availableTo"] = "2022-07-01T00:00:00Z"
    second = _queue(payload)
    first_old = next(item for item in first["work_items"] if item["venue_symbol"] == "OLDUSDT")
    second_old = next(item for item in second["work_items"] if item["venue_symbol"] == "OLDUSDT")
    assert first_old["provider_collection_search_hint_to"] != second_old["provider_collection_search_hint_to"]
    for item in (first_old, second_old):
        assert item["provider_collection_bounds_authority"] == "SEARCH_HINT_ONLY"
        assert item["delisting_time_authority"] == "NONE"
        assert item["negative_control_authority"] == "NONE"
        assert item["cohort_snapshot_authority"] is False


def test_manifest_fingerprint_or_authority_substitution_fails_closed() -> None:
    manifest = _manifest()
    tampered = copy.deepcopy(manifest)
    tampered["manifest_fingerprint"] = "0" * 64
    with pytest.raises(SurvivorshipMetadataError, match="fingerprint mismatch"):
        build_identity_resolution_work_queue(tampered)

    tampered = copy.deepcopy(manifest)
    tampered["historical_membership_authority"] = "MEMBER"
    core = {key: value for key, value in tampered.items() if key != "manifest_fingerprint"}
    tampered["manifest_fingerprint"] = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(SurvivorshipMetadataError, match="unexpectedly grants historical_membership_authority"):
        build_identity_resolution_work_queue(tampered)


def test_queue_rejects_record_that_attempts_cohort_authority() -> None:
    manifest = _manifest()
    tampered = copy.deepcopy(manifest)
    tampered["symbols"][0]["cohort_snapshot_authority"] = True
    core = {key: value for key, value in tampered.items() if key != "manifest_fingerprint"}
    tampered["manifest_fingerprint"] = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(SurvivorshipMetadataError, match="cannot grant cohort snapshot authority"):
        build_identity_resolution_work_queue(tampered)

from __future__ import annotations

import copy

import pytest

from big_move_survivorship_metadata import (
    CONTRACT_ID,
    SurvivorshipMetadataError,
    build_survivorship_enumeration_manifest,
)


SHA = "a" * 64


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


def _manifest(payload: dict | None = None) -> dict:
    return build_survivorship_enumeration_manifest(
        _payload() if payload is None else payload,
        source_response_sha256=SHA,
        captured_at="2026-09-23T02:00:00Z",
    )


def test_inactive_dead_symbol_is_retained_for_identity_enumeration() -> None:
    manifest = _manifest()
    assert manifest["contract_id"] == CONTRACT_ID
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


def test_manifest_fingerprint_is_permutation_stable() -> None:
    one = _manifest()
    payload = _payload()
    payload["datasets"]["symbols"] = list(reversed(payload["datasets"]["symbols"]))
    two = _manifest(payload)
    assert one["manifest_fingerprint"] == two["manifest_fingerprint"]


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
    with pytest.raises(SurvivorshipMetadataError, match="lowercase SHA-256"):
        build_survivorship_enumeration_manifest(
            _payload(), source_response_sha256="not-a-digest", captured_at="2026-09-23T02:00:00Z"
        )

from __future__ import annotations

import pytest

from two_x_subject_binding import (
    FEATURE_SUBJECT_SCOPE,
    SCOPE_ASSET,
    SCOPE_ASSET_VENUE_INSTRUMENT,
    SCOPE_GLOBAL,
    SUBJECT_BINDING_SCHEMA,
    expected_subject_binding_sha256,
    feature_subject_binding_payload,
    feature_subject_binding_sha256,
)


RECORD_SHA = "a" * 64
VENUES = {"BINANCE_SPOT": "TESTUSDT"}


def test_scope_registry_is_explicit_and_market_regime_is_only_global_family() -> None:
    assert FEATURE_SUBJECT_SCOPE["market_regime"] == SCOPE_GLOBAL
    assert [
        family
        for family, scope in FEATURE_SUBJECT_SCOPE.items()
        if scope == SCOPE_GLOBAL
    ] == ["market_regime"]
    assert FEATURE_SUBJECT_SCOPE["stable_identity"] == SCOPE_ASSET
    assert FEATURE_SUBJECT_SCOPE["strict_tradability"] == SCOPE_ASSET_VENUE_INSTRUMENT
    assert FEATURE_SUBJECT_SCOPE["venue_membership"] == SCOPE_ASSET_VENUE_INSTRUMENT


def test_asset_scoped_binding_cannot_be_transplanted_between_assets() -> None:
    asset_a = expected_subject_binding_sha256(
        feature_family="liquidity_proxy",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:a",
        venue_symbols=VENUES,
    )
    asset_b = expected_subject_binding_sha256(
        feature_family="liquidity_proxy",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:b",
        venue_symbols=VENUES,
    )
    assert asset_a != asset_b


def test_venue_instrument_binding_cannot_be_replayed_after_symbol_or_venue_mutation() -> None:
    original = expected_subject_binding_sha256(
        feature_family="strict_tradability",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:test",
        venue_symbols={"BINANCE_SPOT": "TESTUSDT"},
    )
    symbol_mutation = expected_subject_binding_sha256(
        feature_family="strict_tradability",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:test",
        venue_symbols={"BINANCE_SPOT": "OTHERUSDT"},
    )
    venue_mutation = expected_subject_binding_sha256(
        feature_family="strict_tradability",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:test",
        venue_symbols={"COINBASE_SPOT": "TEST-USD"},
    )
    assert original != symbol_mutation
    assert original != venue_mutation


def test_global_market_regime_binding_is_deliberately_reusable_across_assets() -> None:
    direct = feature_subject_binding_sha256(
        feature_family="market_regime",
        feature_record_sha256=RECORD_SHA,
    )
    for asset_id in ("asset:a", "asset:b"):
        assert expected_subject_binding_sha256(
            feature_family="market_regime",
            feature_record_sha256=RECORD_SHA,
            asset_id=asset_id,
            venue_symbols=VENUES,
        ) == direct


def test_payload_binds_schema_scope_family_and_exact_record_digest() -> None:
    payload = feature_subject_binding_payload(
        feature_family="strict_tradability",
        feature_record_sha256=RECORD_SHA,
        asset_id="asset:test",
        venue_symbols={"Z_VENUE": "ZPAIR", "A_VENUE": "APAIR"},
    )
    assert payload == {
        "schema": SUBJECT_BINDING_SCHEMA,
        "scope": SCOPE_ASSET_VENUE_INSTRUMENT,
        "feature_family": "strict_tradability",
        "feature_record_sha256": RECORD_SHA,
        "asset_id": "asset:test",
        "venue_symbols": {"A_VENUE": "APAIR", "Z_VENUE": "ZPAIR"},
    }


def test_binding_rejects_scope_smuggling_and_unknown_family() -> None:
    with pytest.raises(ValueError, match="GLOBAL subject binding"):
        feature_subject_binding_payload(
            feature_family="market_regime",
            feature_record_sha256=RECORD_SHA,
            asset_id="asset:test",
        )
    with pytest.raises(ValueError, match="ASSET subject binding"):
        feature_subject_binding_payload(
            feature_family="liquidity_proxy",
            feature_record_sha256=RECORD_SHA,
            asset_id="asset:test",
            venue_symbols=VENUES,
        )
    with pytest.raises(ValueError, match="unsupported feature family"):
        feature_subject_binding_sha256(
            feature_family="not_a_frozen_family",
            feature_record_sha256=RECORD_SHA,
            asset_id="asset:test",
        )


def test_binding_rejects_malformed_identity_inputs() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        expected_subject_binding_sha256(
            feature_family="liquidity_proxy",
            feature_record_sha256="A" * 64,
            asset_id="asset:test",
            venue_symbols=VENUES,
        )
    with pytest.raises(ValueError, match="bounded safe token"):
        expected_subject_binding_sha256(
            feature_family="liquidity_proxy",
            feature_record_sha256=RECORD_SHA,
            asset_id="asset:test\nspoof",
            venue_symbols=VENUES,
        )
    with pytest.raises(ValueError, match="non-empty bounded mapping"):
        expected_subject_binding_sha256(
            feature_family="strict_tradability",
            feature_record_sha256=RECORD_SHA,
            asset_id="asset:test",
            venue_symbols={},
        )

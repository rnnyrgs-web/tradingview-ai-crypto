from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from money_intelligence.forward_move_ledger import (
    ForecastOutcome,
    ForwardMoveForecast,
    TrustedFormationReceipt,
    receipt_from_store_row,
    resolve_forecast,
    trusted_expires_at,
    verify_formation_receipt,
)


UTC = timezone.utc
FORMED = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
RECEIPT_TIME = FORMED + timedelta(seconds=2)


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _forecast(**overrides):
    values = {
        "asset_id": "ASSET-USD",
        "formed_at": FORMED,
        "evidence_cutoff": FORMED - timedelta(minutes=5),
        "reference_price": "10.00",
        "reference_price_observed_at": FORMED - timedelta(minutes=6),
        "reference_price_source_id": "snapshot:abc",
        "reference_price_observation_id": "binance:ASSETUSDT:1m:20260920T115400Z",
        "reference_price_observation_sha256": _sha("reference-price-row"),
        "evidence_manifest_sha256": _sha("full-pit-evidence-manifest"),
        "horizon_days": 90,
        "evidence_for": ("spot accumulation", "supply contraction"),
        "evidence_against": ("weak macro regime",),
        "invalidation_rules": ("liquidity falls below frozen floor",),
        "target_multiple": "2",
        "source_ids": ("snapshot:abc", "flow:def"),
    }
    values.update(overrides)
    return ForwardMoveForecast(**values)


def _receipt(forecast=None, *, created_at=RECEIPT_TIME, sequence=7):
    forecast = forecast or _forecast()
    return TrustedFormationReceipt(
        sequence=sequence,
        forecast_fingerprint=forecast.fingerprint,
        server_created_at=created_at,
        formation_payload=forecast.to_record(),
    )


def test_formation_fingerprint_is_deterministic_and_order_invariant():
    first = _forecast(
        reference_price="10.000",
        evidence_for=("supply contraction", "spot accumulation", "spot accumulation"),
        source_ids=("flow:def", "snapshot:abc"),
    )
    second = _forecast(reference_price=10)

    assert first.fingerprint == second.fingerprint
    assert first.to_record()["reference_price"] == "10"
    assert first.to_record()["declared_expires_at"] == "2026-12-19T12:00:00Z"
    assert first.to_record()["prospective_status"] == "UNTRUSTED_UNTIL_SERVER_RECEIPT"


def test_formation_is_frozen_and_rejects_future_or_unbound_evidence():
    forecast = _forecast()
    with pytest.raises(FrozenInstanceError):
        forecast.asset_id = "REWRITTEN"  # type: ignore[misc]

    with pytest.raises(ValueError, match="evidence_cutoff"):
        _forecast(evidence_cutoff=FORMED + timedelta(seconds=1))
    with pytest.raises(ValueError, match="reference_price_observed_at"):
        _forecast(reference_price_observed_at=FORMED)
    with pytest.raises(ValueError, match="reference_price_source_id"):
        _forecast(reference_price_source_id="other:source")
    with pytest.raises(ValueError, match="SHA-256"):
        _forecast(evidence_manifest_sha256="caller narrative")


def test_formation_enforces_2x_and_90_day_contract():
    with pytest.raises(ValueError, match="horizon_days"):
        _forecast(horizon_days=91)
    with pytest.raises(ValueError, match="at least 2x"):
        _forecast(target_multiple="1.99")
    with pytest.raises(ValueError, match="evidence_for"):
        _forecast(evidence_for=())
    with pytest.raises(ValueError, match="invalidation_rules"):
        _forecast(invalidation_rules=())


def test_trusted_receipt_binds_full_payload_and_server_time():
    forecast = _forecast()
    receipt = _receipt(forecast)
    verify_formation_receipt(forecast, receipt)
    assert trusted_expires_at(forecast, receipt) == RECEIPT_TIME + timedelta(days=90)

    tampered = dict(forecast.to_record())
    tampered["reference_price"] = "9"
    with pytest.raises(ValueError, match="full frozen formation"):
        verify_formation_receipt(
            forecast,
            TrustedFormationReceipt(
                sequence=7,
                forecast_fingerprint=forecast.fingerprint,
                server_created_at=RECEIPT_TIME,
                formation_payload=tampered,
            ),
        )

    with pytest.raises(ValueError, match="cannot predate declared formation"):
        verify_formation_receipt(
            forecast,
            TrustedFormationReceipt(
                sequence=7,
                forecast_fingerprint=forecast.fingerprint,
                server_created_at=FORMED - timedelta(seconds=1),
                formation_payload=forecast.to_record(),
            ),
        )


def test_store_row_parser_has_no_caller_created_at_fallback():
    forecast = _forecast()
    row = {
        "sequence": 7,
        "forecast_fingerprint": forecast.fingerprint,
        "created_at": "2026-09-20T12:00:02Z",
        "formation_payload": forecast.to_record(),
    }
    receipt = receipt_from_store_row(row)
    verify_formation_receipt(forecast, receipt)
    assert receipt.server_created_at == RECEIPT_TIME

    bad = dict(row)
    bad.pop("created_at")
    with pytest.raises(ValueError, match="created_at"):
        receipt_from_store_row(bad)


def test_backdated_forecast_after_move_cannot_count_as_early_prediction():
    attacker_formed = FORMED - timedelta(days=1)
    forecast = _forecast(
        formed_at=attacker_formed,
        evidence_cutoff=attacker_formed - timedelta(minutes=1),
        reference_price_observed_at=attacker_formed - timedelta(minutes=2),
    )
    receipt = _receipt(forecast, created_at=RECEIPT_TIME)
    move_happened_before_receipt = FORMED - timedelta(hours=1)

    with pytest.raises(ValueError, match="retroactive"):
        resolve_forecast(
            forecast,
            receipt,
            resolved_at=RECEIPT_TIME + timedelta(minutes=1),
            observation_start_at=RECEIPT_TIME,
            observation_end_at=RECEIPT_TIME + timedelta(minutes=1),
            observed_max_price="21",
            first_target_hit_at=move_happened_before_receipt,
        )


def test_hit_requires_point_in_time_hit_timestamp_after_trusted_formation():
    forecast = _forecast()
    receipt = _receipt(forecast)
    hit_at = RECEIPT_TIME + timedelta(days=12)
    resolution = resolve_forecast(
        forecast,
        receipt,
        resolved_at=hit_at + timedelta(minutes=1),
        observation_start_at=RECEIPT_TIME,
        observation_end_at=hit_at,
        observed_max_price="20.5",
        first_target_hit_at=hit_at,
    )

    assert resolution.outcome is ForecastOutcome.HIT
    assert resolution.forecast_fingerprint == forecast.fingerprint
    assert resolution.formation_receipt_fingerprint == receipt.fingerprint
    assert resolution.formation_receipt_sequence == 7
    assert resolution.to_record()["first_target_hit_at"] == "2026-10-02T12:00:02Z"
    assert "evidence_for" not in resolution.to_record()

    with pytest.raises(ValueError, match="point-in-time"):
        resolve_forecast(
            forecast,
            receipt,
            resolved_at=hit_at,
            observation_start_at=RECEIPT_TIME,
            observation_end_at=hit_at,
            observed_max_price="20.5",
        )


def test_invalidation_before_hit_wins_and_does_not_rewrite_formation():
    forecast = _forecast()
    receipt = _receipt(forecast)
    invalidated_at = RECEIPT_TIME + timedelta(days=8)
    later_hit = RECEIPT_TIME + timedelta(days=10)
    resolution = resolve_forecast(
        forecast,
        receipt,
        resolved_at=later_hit,
        observation_start_at=RECEIPT_TIME,
        observation_end_at=later_hit,
        observed_max_price="22",
        first_target_hit_at=later_hit,
        invalidation_at=invalidated_at,
    )

    assert resolution.outcome is ForecastOutcome.INVALIDATED
    assert resolution.forecast_fingerprint == forecast.fingerprint


def test_expiry_requires_complete_trusted_horizon():
    forecast = _forecast(horizon_days=30)
    receipt = _receipt(forecast)
    expiry = RECEIPT_TIME + timedelta(days=30)

    with pytest.raises(ValueError, match="still open"):
        resolve_forecast(
            forecast,
            receipt,
            resolved_at=RECEIPT_TIME + timedelta(days=10),
            observation_start_at=RECEIPT_TIME,
            observation_end_at=RECEIPT_TIME + timedelta(days=10),
            observed_max_price="17",
        )

    resolution = resolve_forecast(
        forecast,
        receipt,
        resolved_at=expiry + timedelta(minutes=1),
        observation_start_at=RECEIPT_TIME,
        observation_end_at=expiry,
        observed_max_price="19.99",
    )
    assert resolution.outcome is ForecastOutcome.EXPIRED


def test_resolution_window_cannot_include_pre_receipt_or_posthorizon_prices():
    forecast = _forecast(horizon_days=30)
    receipt = _receipt(forecast)

    with pytest.raises(ValueError, match="trusted server receipt time"):
        resolve_forecast(
            forecast,
            receipt,
            resolved_at=RECEIPT_TIME + timedelta(days=1),
            observation_start_at=FORMED,
            observation_end_at=RECEIPT_TIME + timedelta(days=1),
            observed_max_price="15",
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        resolve_forecast(
            forecast,
            receipt,
            resolved_at=RECEIPT_TIME + timedelta(days=31),
            observation_start_at=RECEIPT_TIME,
            observation_end_at=RECEIPT_TIME + timedelta(days=31),
            observed_max_price="15",
        )


def test_sql_store_withholds_direct_insert_and_requires_bound_reference_receipt():
    root = Path(__file__).parents[1]
    sql = (root / "supabase/migrations/20260921051500_big_move_forward_formations.sql").read_text()
    assert "default clock_timestamp()" in sql
    assert "grant insert (forecast_fingerprint, formation_payload)" not in sql
    assert "revoke all on table public.big_move_forward_formations" in sql
    assert "append_big_move_reference_observation_v1" in sql
    assert "append_big_move_forward_formation_v1" in sql
    assert "p_reference_observation_sequence bigint" in sql
    assert "references public.big_move_reference_observations(sequence)" in sql

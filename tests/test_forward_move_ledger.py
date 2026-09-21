from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from money_intelligence.forward_move_ledger import (
    ForecastOutcome,
    ForwardMoveForecast,
    resolve_forecast,
)


UTC = timezone.utc
FORMED = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def _forecast(**overrides):
    values = {
        "asset_id": "ASSET-USD",
        "formed_at": FORMED,
        "evidence_cutoff": FORMED - timedelta(minutes=5),
        "reference_price": "10.00",
        "horizon_days": 90,
        "evidence_for": ("spot accumulation", "supply contraction"),
        "evidence_against": ("weak macro regime",),
        "invalidation_rules": ("liquidity falls below frozen floor",),
        "target_multiple": "2",
        "source_ids": ("snapshot:abc", "flow:def"),
    }
    values.update(overrides)
    return ForwardMoveForecast(**values)


def test_formation_fingerprint_is_deterministic_and_order_invariant():
    first = _forecast(
        reference_price="10.000",
        evidence_for=("supply contraction", "spot accumulation", "spot accumulation"),
        source_ids=("flow:def", "snapshot:abc"),
    )
    second = _forecast(reference_price=10)

    assert first.fingerprint == second.fingerprint
    assert first.to_record()["reference_price"] == "10"
    assert first.to_record()["expires_at"] == "2026-12-19T12:00:00Z"


def test_formation_is_frozen_and_rejects_future_evidence():
    forecast = _forecast()
    with pytest.raises(FrozenInstanceError):
        forecast.asset_id = "REWRITTEN"  # type: ignore[misc]

    with pytest.raises(ValueError, match="evidence_cutoff"):
        _forecast(evidence_cutoff=FORMED + timedelta(seconds=1))


def test_formation_enforces_2x_and_90_day_contract():
    with pytest.raises(ValueError, match="horizon_days"):
        _forecast(horizon_days=91)
    with pytest.raises(ValueError, match="at least 2x"):
        _forecast(target_multiple="1.99")
    with pytest.raises(ValueError, match="evidence_for"):
        _forecast(evidence_for=())
    with pytest.raises(ValueError, match="invalidation_rules"):
        _forecast(invalidation_rules=())


def test_retroactive_target_hit_can_never_be_counted_as_prediction():
    forecast = _forecast()
    with pytest.raises(ValueError, match="retroactive"):
        resolve_forecast(
            forecast,
            resolved_at=FORMED + timedelta(days=1),
            observation_start_at=FORMED,
            observation_end_at=FORMED + timedelta(days=1),
            observed_max_price="21",
            first_target_hit_at=FORMED,
        )


def test_hit_requires_point_in_time_hit_timestamp_after_formation():
    forecast = _forecast()
    hit_at = FORMED + timedelta(days=12)
    resolution = resolve_forecast(
        forecast,
        resolved_at=hit_at + timedelta(minutes=1),
        observation_start_at=FORMED,
        observation_end_at=hit_at,
        observed_max_price="20.5",
        first_target_hit_at=hit_at,
    )

    assert resolution.outcome is ForecastOutcome.HIT
    assert resolution.forecast_fingerprint == forecast.fingerprint
    assert resolution.to_record()["first_target_hit_at"] == "2026-10-02T12:00:00Z"
    assert "evidence_for" not in resolution.to_record()

    with pytest.raises(ValueError, match="point-in-time"):
        resolve_forecast(
            forecast,
            resolved_at=hit_at,
            observation_start_at=FORMED,
            observation_end_at=hit_at,
            observed_max_price="20.5",
        )


def test_invalidation_before_hit_wins_and_does_not_rewrite_formation():
    forecast = _forecast()
    invalidated_at = FORMED + timedelta(days=8)
    later_hit = FORMED + timedelta(days=10)
    resolution = resolve_forecast(
        forecast,
        resolved_at=later_hit,
        observation_start_at=FORMED,
        observation_end_at=later_hit,
        observed_max_price="22",
        first_target_hit_at=later_hit,
        invalidation_at=invalidated_at,
    )

    assert resolution.outcome is ForecastOutcome.INVALIDATED
    assert resolution.forecast_fingerprint == forecast.fingerprint


def test_expiry_requires_complete_frozen_horizon():
    forecast = _forecast(horizon_days=30)
    expiry = FORMED + timedelta(days=30)

    with pytest.raises(ValueError, match="still open"):
        resolve_forecast(
            forecast,
            resolved_at=FORMED + timedelta(days=10),
            observation_start_at=FORMED,
            observation_end_at=FORMED + timedelta(days=10),
            observed_max_price="17",
        )

    resolution = resolve_forecast(
        forecast,
        resolved_at=expiry + timedelta(minutes=1),
        observation_start_at=FORMED,
        observation_end_at=expiry,
        observed_max_price="19.99",
    )
    assert resolution.outcome is ForecastOutcome.EXPIRED


def test_resolution_window_cannot_include_preformation_or_posthorizon_prices():
    forecast = _forecast(horizon_days=30)

    with pytest.raises(ValueError, match="must equal"):
        resolve_forecast(
            forecast,
            resolved_at=FORMED + timedelta(days=1),
            observation_start_at=FORMED - timedelta(seconds=1),
            observation_end_at=FORMED + timedelta(days=1),
            observed_max_price="15",
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        resolve_forecast(
            forecast,
            resolved_at=FORMED + timedelta(days=31),
            observation_start_at=FORMED,
            observation_end_at=FORMED + timedelta(days=31),
            observed_max_price="15",
        )

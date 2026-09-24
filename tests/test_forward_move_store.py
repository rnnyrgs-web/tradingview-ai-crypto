from datetime import datetime, timedelta, timezone
import hashlib

import pytest

import money_intelligence.forward_move_store as store
from money_intelligence.forward_move_ledger import ForwardMoveForecast
from money_intelligence.trusted_reference_store import (
    DB_SOURCE_ID,
    TrustedReferenceReceipt,
)


UTC = timezone.utc
OBSERVED = datetime(2026, 9, 21, 8, 0, 0, tzinfo=UTC)
CAPTURED = OBSERVED + timedelta(seconds=2)
REFERENCE_RECEIPT_AT = CAPTURED + timedelta(seconds=1)
FORMED = REFERENCE_RECEIPT_AT + timedelta(seconds=1)
EVIDENCE_SHA = hashlib.sha256(b"trusted-reference-evidence").hexdigest()
MANIFEST_SHA = hashlib.sha256(b"pit-evidence-manifest").hexdigest()


def _reference_receipt(**overrides):
    values = dict(
        sequence=41,
        asset_id="ASSETUSDT",
        reference_price="10",
        observed_at=OBSERVED,
        captured_at=CAPTURED,
        server_created_at=REFERENCE_RECEIPT_AT,
        source_id=DB_SOURCE_ID,
        evidence_sha256=EVIDENCE_SHA,
        evidence={"fixture": True},
    )
    values.update(overrides)
    return TrustedReferenceReceipt(**values)


def _forecast(reference=None, **overrides):
    reference = reference or _reference_receipt()
    values = dict(
        asset_id=reference.asset_id,
        formed_at=FORMED,
        evidence_cutoff=FORMED,
        reference_price=reference.reference_price,
        reference_price_observed_at=reference.observed_at,
        reference_price_source_id=reference.source_id,
        reference_price_observation_id=reference.observation_id,
        reference_price_observation_sha256=reference.evidence_sha256,
        evidence_manifest_sha256=MANIFEST_SHA,
        horizon_days=90,
        evidence_for=("PIT precursor",),
        evidence_against=("PIT contradiction retained",),
        invalidation_rules=("frozen invalidation",),
        target_multiple="2",
        source_ids=(reference.source_id,),
    )
    values.update(overrides)
    return ForwardMoveForecast(**values)


def test_forecast_must_exactly_match_durable_reference_receipt():
    reference = _reference_receipt()
    forecast = _forecast(reference)
    store.verify_forecast_reference_receipt(forecast, reference)

    with pytest.raises(ValueError, match="reference price"):
        store.verify_forecast_reference_receipt(
            _forecast(reference, reference_price="9"), reference
        )
    with pytest.raises(ValueError, match="observation id"):
        store.verify_forecast_reference_receipt(
            _forecast(reference, reference_price_observation_id="caller:fake"), reference
        )
    with pytest.raises(ValueError, match="evidence SHA"):
        store.verify_forecast_reference_receipt(
            _forecast(
                reference,
                reference_price_observation_sha256=hashlib.sha256(b"other").hexdigest(),
            ),
            reference,
        )


def test_forecast_cannot_claim_formation_before_reference_receipt():
    reference = _reference_receipt()
    forecast = _forecast(
        reference,
        formed_at=REFERENCE_RECEIPT_AT - timedelta(seconds=1),
        evidence_cutoff=REFERENCE_RECEIPT_AT - timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="before durable reference receipt"):
        store.verify_forecast_reference_receipt(forecast, reference)


def test_bound_store_row_rejects_different_reference_sequence(monkeypatch):
    reference = _reference_receipt()
    forecast = _forecast(reference)
    row = {
        "sequence": 7,
        "forecast_fingerprint": forecast.fingerprint,
        "reference_observation_sequence": reference.sequence + 1,
        "reference_observation_created_at": REFERENCE_RECEIPT_AT.isoformat().replace("+00:00", "Z"),
        "reference_observation": {},
        "created_at": (FORMED + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "formation_payload": forecast.to_record(),
    }
    monkeypatch.setattr(store, "reference_receipt_from_store_row", lambda value: reference)
    with pytest.raises(ValueError, match="unexpected reference observation"):
        store.formation_receipt_from_bound_store_row(forecast, reference, row)


def test_bound_store_row_rejects_different_reference_payload(monkeypatch):
    reference = _reference_receipt()
    forecast = _forecast(reference)
    different = _reference_receipt(reference_price="11")
    row = {
        "sequence": 7,
        "forecast_fingerprint": forecast.fingerprint,
        "reference_observation_sequence": reference.sequence,
        "reference_observation_created_at": REFERENCE_RECEIPT_AT.isoformat().replace("+00:00", "Z"),
        "reference_observation": {"placeholder": True},
        "created_at": (FORMED + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "formation_payload": forecast.to_record(),
    }
    monkeypatch.setattr(store, "reference_receipt_from_store_row", lambda value: different)
    with pytest.raises(ValueError, match="different durable reference observation"):
        store.formation_receipt_from_bound_store_row(forecast, reference, row)

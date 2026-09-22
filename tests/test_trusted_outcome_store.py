from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import inspect
import json

import pytest

from money_intelligence.forward_move_ledger import ForwardMoveForecast, TrustedFormationReceipt
from money_intelligence.trusted_outcome_store import (
    OUTCOME_TRUST_STATUS,
    _binding_preimage,
    capture_and_persist_trusted_outcome_observation,
    derive_trusted_hit_evidence,
    outcome_observation_receipt_from_store_row,
    verify_outcome_observation_receipt,
)
from money_intelligence.trusted_reference_store import (
    DB_EVIDENCE_SCHEMA,
    DB_SOURCE_ID,
    _evidence_preimage,
)


UTC = timezone.utc
FORMED = datetime(2026, 9, 21, 8, 0, 5, tzinfo=UTC)
FORMATION_RECEIPT_AT = FORMED + timedelta(seconds=1)
MANIFEST_SHA = hashlib.sha256(b"frozen-pit-manifest").hexdigest()
REFERENCE_SHA = hashlib.sha256(b"trusted-formation-reference").hexdigest()


def _ms(value):
    return int(value.timestamp() * 1000)


def _forecast(**overrides):
    values = dict(
        asset_id="ASSETUSDT",
        formed_at=FORMED,
        evidence_cutoff=FORMED,
        reference_price="10",
        reference_price_observed_at=FORMED - timedelta(seconds=2),
        reference_price_source_id=DB_SOURCE_ID,
        reference_price_observation_id="big_move_reference:41",
        reference_price_observation_sha256=REFERENCE_SHA,
        evidence_manifest_sha256=MANIFEST_SHA,
        horizon_days=90,
        evidence_for=("PIT precursor",),
        evidence_against=("PIT contradiction retained",),
        invalidation_rules=("machine-verifiable rule pending",),
        target_multiple="2",
        source_ids=(DB_SOURCE_ID,),
    )
    values.update(overrides)
    return ForwardMoveForecast(**values)


def _formation_receipt(forecast=None):
    forecast = forecast or _forecast()
    return TrustedFormationReceipt(
        sequence=7,
        forecast_fingerprint=forecast.fingerprint,
        server_created_at=FORMATION_RECEIPT_AT,
        formation_payload=forecast.to_record(),
    )


def _source_row(*, sequence, price, captured_at):
    binance_observed = captured_at - timedelta(seconds=2)
    okx_observed = captured_at - timedelta(seconds=1)
    binance_raw = json.dumps(
        {
            "symbol": "ASSETUSDT",
            "lastPrice": str(price),
            "closeTime": _ms(binance_observed),
        },
        separators=(",", ":"),
    ).encode()
    okx_raw = json.dumps(
        {
            "code": "0",
            "data": [
                {
                    "instId": "ASSET-USDT",
                    "last": str(price),
                    "ts": str(_ms(okx_observed)),
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    binance_sha = hashlib.sha256(binance_raw).hexdigest()
    okx_sha = hashlib.sha256(okx_raw).hexdigest()
    normalized_price = str(price).rstrip("0").rstrip(".") if "." in str(price) else str(price)
    evidence_sha = hashlib.sha256(
        _evidence_preimage(
            asset_id="ASSETUSDT",
            binance_symbol="ASSETUSDT",
            binance_raw_sha256=binance_sha,
            okx_inst_id="ASSET-USDT",
            okx_raw_sha256=okx_sha,
            captured_at=captured_at,
            reference_price=normalized_price,
        )
    ).hexdigest()
    evidence = {
        "schema": DB_EVIDENCE_SCHEMA,
        "source_id": DB_SOURCE_ID,
        "asset_id": "ASSETUSDT",
        "captured_at": captured_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "reference_price": normalized_price,
        "cross_venue_deviation_bps": "0",
        "derivation": {
            "method": "ARITHMETIC_MIDPOINT_OF_DB_FETCHED_SPOT_LAST_PRICES",
            "version": "2",
            "max_provider_age_seconds": 120,
            "max_cross_venue_deviation_bps": "75",
            "provider_fetch_authority": "POSTGRES_HTTP_EXTENSION_FIXED_ENDPOINTS",
        },
        "providers": [
            {
                "venue": "BINANCE_SPOT",
                "symbol": "ASSETUSDT",
                "price": normalized_price,
                "observed_at": binance_observed.isoformat().replace("+00:00", "Z"),
                "raw_response_sha256": binance_sha,
                "raw_response_utf8": binance_raw.decode(),
            },
            {
                "venue": "OKX_SPOT",
                "symbol": "ASSET-USDT",
                "price": normalized_price,
                "observed_at": okx_observed.isoformat().replace("+00:00", "Z"),
                "raw_response_sha256": okx_sha,
                "raw_response_utf8": okx_raw.decode(),
            },
        ],
    }
    return {
        "sequence": sequence,
        "asset_id": "ASSETUSDT",
        "reference_price": normalized_price,
        "observed_at": okx_observed.isoformat(),
        "captured_at": captured_at.isoformat(),
        "created_at": (captured_at + timedelta(milliseconds=100)).isoformat(),
        "source_id": DB_SOURCE_ID,
        "evidence_sha256": evidence_sha,
        "evidence": evidence,
    }


def _outcome_row(*, sequence, source_sequence, price, captured_at, forecast=None):
    forecast = forecast or _forecast()
    source = _source_row(sequence=source_sequence, price=price, captured_at=captured_at)
    observed_at = datetime.fromisoformat(source["observed_at"])
    binding = hashlib.sha256(
        _binding_preimage(
            formation_sequence=7,
            formation_fingerprint=forecast.fingerprint,
            source_reference_sequence=source_sequence,
            asset_id="ASSETUSDT",
            source_evidence_sha256=source["evidence_sha256"],
            observed_price=source["reference_price"],
            observed_at=observed_at,
            captured_at=captured_at,
        )
    ).hexdigest()
    return {
        "sequence": sequence,
        "formation_sequence": 7,
        "formation_fingerprint": forecast.fingerprint,
        "source_reference_observation_sequence": source_sequence,
        "asset_id": "ASSETUSDT",
        "observed_price": source["reference_price"],
        "observed_at": source["observed_at"],
        "captured_at": source["captured_at"],
        "source_evidence_sha256": source["evidence_sha256"],
        "binding_sha256": binding,
        "created_at": (captured_at + timedelta(milliseconds=200)).isoformat(),
        "source_reference_observation": source,
    }


def test_trusted_outcome_receipt_reproduces_provider_and_formation_binding():
    forecast = _forecast()
    formation = _formation_receipt(forecast)
    row = _outcome_row(
        sequence=1,
        source_sequence=101,
        price="15.0",
        captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
        forecast=forecast,
    )
    receipt = outcome_observation_receipt_from_store_row(row)
    verify_outcome_observation_receipt(forecast, formation, receipt)
    assert receipt.asset_id == "ASSETUSDT"
    assert receipt.observed_price == "15"
    assert receipt.source_reference_receipt.asset_id == "ASSETUSDT"


def test_cross_asset_and_cross_venue_substitution_are_rejected():
    row = _outcome_row(
        sequence=1,
        source_sequence=101,
        price="15",
        captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
    )
    cross_asset = dict(row)
    cross_asset["asset_id"] = "OTHERUSDT"
    with pytest.raises(ValueError, match="source asset"):
        outcome_observation_receipt_from_store_row(cross_asset)

    cross_venue = _outcome_row(
        sequence=1,
        source_sequence=101,
        price="15",
        captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
    )
    cross_venue["source_reference_observation"]["evidence"]["providers"][1]["symbol"] = "OTHER-USDT"
    with pytest.raises(ValueError, match="cross-venue identity mismatch"):
        outcome_observation_receipt_from_store_row(cross_venue)


def test_binding_tamper_and_preformation_evidence_are_rejected():
    row = _outcome_row(
        sequence=1,
        source_sequence=101,
        price="15",
        captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
    )
    row["binding_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="binding SHA-256"):
        outcome_observation_receipt_from_store_row(row)

    forecast = _forecast()
    formation = _formation_receipt(forecast)
    pre = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=2,
            source_sequence=102,
            price="15",
            captured_at=FORMATION_RECEIPT_AT - timedelta(milliseconds=100),
            forecast=forecast,
        )
    )
    with pytest.raises(ValueError, match="pre-formation"):
        verify_outcome_observation_receipt(forecast, formation, pre)


def test_hit_evidence_is_derived_only_from_verified_ordered_receipts():
    forecast = _forecast()
    formation = _formation_receipt(forecast)
    first = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=1,
            source_sequence=101,
            price="15",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
            forecast=forecast,
        )
    )
    hit = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=2,
            source_sequence=102,
            price="20.5",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=10),
            forecast=forecast,
        )
    )
    later = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=3,
            source_sequence=103,
            price="25",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=15),
            forecast=forecast,
        )
    )

    evidence = derive_trusted_hit_evidence(forecast, formation, [later, hit, first])
    assert evidence.target_price == "20"
    assert evidence.observed_max_price == "20.5"
    assert evidence.observation_sequences == (1, 2)
    assert evidence.first_trusted_hit_observed_at == hit.observed_at
    assert evidence.trust_status == OUTCOME_TRUST_STATUS

    with pytest.raises(ValueError, match="do not prove a target hit"):
        derive_trusted_hit_evidence(forecast, formation, [first])


def test_authoritative_capture_api_accepts_no_market_values_or_instruments():
    signature = inspect.signature(capture_and_persist_trusted_outcome_observation)
    assert set(signature.parameters) == {"forecast", "formation_receipt"}
    assert not {"price", "observed_at", "binance_symbol", "okx_inst_id"} & set(signature.parameters)


def test_sql_boundary_derives_instruments_and_withholds_direct_mutation():
    root = Path(__file__).parents[1]
    sql = (
        root
        / "supabase/migrations/20260922030000_big_move_trusted_outcome_observations.sql"
    ).read_text()
    assert "append_big_move_forward_outcome_observation_v1" in sql
    assert "p_formation_sequence bigint" in sql
    assert "append_big_move_reference_observation_v1(v_asset_id, v_okx_inst_id)" in sql
    assert "v_okx_inst_id := v_base || '-USDT'" in sql
    assert "revoke all on table public.big_move_forward_outcome_observations" in sql
    assert "before update or delete" in sql
    assert "p_observed_price" not in sql
    assert "p_binance_symbol" not in sql
    assert "p_okx_inst_id" not in sql

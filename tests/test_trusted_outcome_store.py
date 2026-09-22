from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import inspect
import json

import pytest

from money_intelligence.forward_move_ledger import ForwardMoveForecast, TrustedFormationReceipt
import money_intelligence.trusted_outcome_store as outcome_store
from money_intelligence.trusted_outcome_store import (
    OUTCOME_TRUST_STATUS,
    PARSED_OUTCOME_STATUS,
    _binding_preimage,
    _formation_receipt_fingerprint,
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


def _formation_receipt(forecast=None, *, sequence=7, created_at=FORMATION_RECEIPT_AT):
    forecast = forecast or _forecast()
    return TrustedFormationReceipt(
        sequence=sequence,
        forecast_fingerprint=forecast.fingerprint,
        server_created_at=created_at,
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


def _outcome_row(
    *,
    sequence,
    source_sequence,
    price,
    captured_at,
    forecast=None,
    formation=None,
    formation_receipt_fingerprint_override=None,
):
    forecast = forecast or _forecast()
    formation = formation or _formation_receipt(forecast)
    source = _source_row(sequence=source_sequence, price=price, captured_at=captured_at)
    observed_at = datetime.fromisoformat(source["observed_at"])
    receipt_fingerprint = (
        formation_receipt_fingerprint_override
        or _formation_receipt_fingerprint(formation)
    )
    binding = hashlib.sha256(
        _binding_preimage(
            formation_sequence=formation.sequence,
            forecast_fingerprint=forecast.fingerprint,
            formation_receipt_fingerprint=receipt_fingerprint,
            asset_id="ASSETUSDT",
            binance_symbol="ASSETUSDT",
            okx_inst_id="ASSET-USDT",
            source_reference_sequence=source_sequence,
            source_evidence_sha256=source["evidence_sha256"],
            observed_price=source["reference_price"],
            observed_at=observed_at,
            captured_at=captured_at,
        )
    ).hexdigest()
    return {
        "sequence": sequence,
        "formation_sequence": formation.sequence,
        "forecast_fingerprint": forecast.fingerprint,
        "formation_receipt_fingerprint": receipt_fingerprint,
        "source_reference_observation_sequence": source_sequence,
        "asset_id": "ASSETUSDT",
        "binance_symbol": "ASSETUSDT",
        "okx_inst_id": "ASSET-USDT",
        "observed_price": source["reference_price"],
        "observed_at": source["observed_at"],
        "captured_at": source["captured_at"],
        "source_evidence_sha256": source["evidence_sha256"],
        "binding_sha256": binding,
        "created_at": (captured_at + timedelta(milliseconds=200)).isoformat(),
        "source_reference_observation": source,
    }


def _db_hit_row(*, price="20.5", captured_at=None, forecast=None, formation=None):
    forecast = forecast or _forecast()
    formation = formation or _formation_receipt(forecast)
    captured_at = captured_at or (formation.server_created_at + timedelta(minutes=10))
    return {
        "formation_sequence": formation.sequence,
        "forecast_fingerprint": forecast.fingerprint,
        "formation_receipt_fingerprint": _formation_receipt_fingerprint(formation),
        "target_price": str(forecast.target_price),
        "breach_observation": _outcome_row(
            sequence=2,
            source_sequence=102,
            price=price,
            captured_at=captured_at,
            forecast=forecast,
            formation=formation,
        ),
    }


def test_parsed_outcome_reproduces_provider_and_full_subject_binding_without_authority():
    forecast = _forecast()
    formation = _formation_receipt(forecast)
    row = _outcome_row(
        sequence=1,
        source_sequence=101,
        price="15.0",
        captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
        forecast=forecast,
        formation=formation,
    )
    parsed = outcome_observation_receipt_from_store_row(row)
    verify_outcome_observation_receipt(forecast, formation, parsed)
    assert parsed.asset_id == "ASSETUSDT"
    assert parsed.binance_symbol == "ASSETUSDT"
    assert parsed.okx_inst_id == "ASSET-USDT"
    assert parsed.observed_price == "15"
    assert parsed.source_reference_receipt.asset_id == "ASSETUSDT"
    assert parsed.trust_status == PARSED_OUTCOME_STATUS


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
    cross_venue["okx_inst_id"] = "OTHER-USDT"
    with pytest.raises(ValueError, match="venue/instrument"):
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
            formation=formation,
        )
    )
    with pytest.raises(ValueError, match="pre-formation"):
        verify_outcome_observation_receipt(forecast, formation, pre)


def test_formation_receipt_fingerprint_tamper_fails_even_with_recomputed_binding():
    forecast = _forecast()
    formation = _formation_receipt(forecast)
    forged_receipt_fingerprint = "a" * 64
    assert forged_receipt_fingerprint != _formation_receipt_fingerprint(formation)
    parsed = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=1,
            source_sequence=101,
            price="15",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
            forecast=forecast,
            formation=formation,
            formation_receipt_fingerprint_override=forged_receipt_fingerprint,
        )
    )
    with pytest.raises(ValueError, match="formation receipt fingerprint"):
        verify_outcome_observation_receipt(forecast, formation, parsed)


def test_cross_formation_transplant_fails_with_same_forecast_asset_and_provider_evidence():
    forecast = _forecast()
    formation_a = _formation_receipt(forecast, sequence=7)
    formation_b = _formation_receipt(
        forecast,
        sequence=8,
        created_at=FORMATION_RECEIPT_AT + timedelta(seconds=1),
    )
    parsed_a = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=1,
            source_sequence=101,
            price="20.5",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
            forecast=forecast,
            formation=formation_a,
        )
    )
    with pytest.raises(ValueError, match="different formation sequence"):
        verify_outcome_observation_receipt(forecast, formation_b, parsed_a)


def test_locally_fabricated_valid_hashes_remain_untrusted_and_cannot_mint_hit(monkeypatch):
    forecast = _forecast()
    formation = _formation_receipt(forecast)

    # These bytes and both public hashes are entirely caller-created, exactly the
    # attack that the previous API accidentally upgraded to a TrustedHitEvidence.
    locally_fabricated = outcome_observation_receipt_from_store_row(
        _outcome_row(
            sequence=999,
            source_sequence=9999,
            price="25",
            captured_at=FORMATION_RECEIPT_AT + timedelta(minutes=5),
            forecast=forecast,
            formation=formation,
        )
    )
    assert locally_fabricated.trust_status == PARSED_OUTCOME_STATUS
    assert locally_fabricated.observed_price == "25"

    # Public trusted-HIT derivation has no observations argument and re-enters the DB.
    assert set(inspect.signature(derive_trusted_hit_evidence).parameters) == {
        "forecast",
        "formation_receipt",
    }
    monkeypatch.setattr(outcome_store, "_db_derived_hit_row", lambda _sequence: None)
    with pytest.raises(ValueError, match="authoritative stored observations"):
        derive_trusted_hit_evidence(forecast, formation)


def test_db_derived_breach_can_mint_only_nonfinal_hit_evidence(monkeypatch):
    forecast = _forecast()
    formation = _formation_receipt(forecast)
    db_row = _db_hit_row(forecast=forecast, formation=formation)
    monkeypatch.setattr(outcome_store, "_db_derived_hit_row", lambda _sequence: db_row)

    evidence = derive_trusted_hit_evidence(forecast, formation)
    assert evidence.target_price == "20"
    assert evidence.observed_price == "20.5"
    assert evidence.observation_sequence == 2
    assert evidence.formation_receipt_fingerprint == _formation_receipt_fingerprint(formation)
    assert evidence.trust_status == OUTCOME_TRUST_STATUS
    assert evidence.breach_observed_at == datetime.fromisoformat(
        db_row["breach_observation"]["observed_at"]
    )


def test_db_derived_hit_rejects_wrong_target_or_formation_receipt(monkeypatch):
    forecast = _forecast()
    formation = _formation_receipt(forecast)

    wrong_target = _db_hit_row(forecast=forecast, formation=formation)
    wrong_target["target_price"] = "19"
    monkeypatch.setattr(outcome_store, "_db_derived_hit_row", lambda _sequence: wrong_target)
    with pytest.raises(ValueError, match="target price"):
        derive_trusted_hit_evidence(forecast, formation)

    wrong_receipt = _db_hit_row(forecast=forecast, formation=formation)
    wrong_receipt["formation_receipt_fingerprint"] = "b" * 64
    monkeypatch.setattr(outcome_store, "_db_derived_hit_row", lambda _sequence: wrong_receipt)
    with pytest.raises(ValueError, match="different formation receipt"):
        derive_trusted_hit_evidence(forecast, formation)


def test_authoritative_capture_api_accepts_no_market_values_or_instruments():
    signature = inspect.signature(capture_and_persist_trusted_outcome_observation)
    assert set(signature.parameters) == {"forecast", "formation_receipt"}
    assert not {"price", "observed_at", "binance_symbol", "okx_inst_id"} & set(signature.parameters)


def test_sql_boundary_derives_full_identity_and_withholds_direct_mutation():
    root = Path(__file__).parents[1]
    sql = (
        root
        / "supabase/migrations/20260922030000_big_move_trusted_outcome_observations.sql"
    ).read_text()
    assert "append_big_move_forward_outcome_observation_v1" in sql
    assert "p_formation_sequence bigint" in sql
    assert "append_big_move_reference_observation_v1(v_binance_symbol, v_okx_inst_id)" in sql
    assert "trusted_forward_formation_receipt_binding.v1" in sql
    assert "trusted_forward_outcome_observation.v2" in sql
    assert "formation_receipt_fingerprint" in sql
    assert "binance_symbol" in sql
    assert "okx_inst_id" in sql
    assert "revoke all on table public.big_move_forward_outcome_observations" in sql
    assert "before update or delete" in sql
    assert "p_observed_price" not in sql
    assert "p_binance_symbol" not in sql
    assert "p_okx_inst_id" not in sql


def test_sql_trusted_hit_derivation_reads_durable_rows_and_has_no_caller_evidence_input():
    root = Path(__file__).parents[1]
    sql = (
        root
        / "supabase/migrations/20260922030000_big_move_trusted_outcome_observations.sql"
    ).read_text()
    assert "derive_big_move_forward_hit_evidence_v1" in sql
    assert "from public.big_move_forward_outcome_observations o" in sql
    assert "o.observed_price >= v_target_price" in sql
    assert "order by o.observed_at, o.captured_at, o.sequence" in sql
    assert "grant execute on function public.derive_big_move_forward_hit_evidence_v1(bigint)" in sql
    assert "p_observations" not in sql
    assert "p_binding_sha256" not in sql

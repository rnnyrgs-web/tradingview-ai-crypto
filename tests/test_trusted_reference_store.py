from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json

import pytest

from money_intelligence.trusted_reference_price import TrustedReferenceCapture
from money_intelligence.trusted_reference_store import (
    DB_EVIDENCE_SCHEMA,
    DB_SOURCE_ID,
    _evidence_preimage,
    capture_and_persist_trusted_reference,
    persist_trusted_reference_capture,
    reference_receipt_from_store_row,
)


UTC = timezone.utc
CAPTURED = datetime(2026, 9, 21, 8, 0, 2, tzinfo=UTC)
BINANCE_OBSERVED = CAPTURED - timedelta(seconds=2)
OKX_OBSERVED = CAPTURED - timedelta(seconds=1)
CREATED = CAPTURED + timedelta(milliseconds=250)


def _ms(value):
    return int(value.timestamp() * 1000)


def _valid_row():
    binance_raw = json.dumps(
        {
            "symbol": "ASSETUSDT",
            "lastPrice": "10.00",
            "closeTime": _ms(BINANCE_OBSERVED),
        },
        separators=(",", ":"),
    ).encode()
    okx_raw = json.dumps(
        {
            "code": "0",
            "data": [
                {
                    "instId": "ASSET-USDT",
                    "last": "10.00",
                    "ts": str(_ms(OKX_OBSERVED)),
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    binance_sha = hashlib.sha256(binance_raw).hexdigest()
    okx_sha = hashlib.sha256(okx_raw).hexdigest()
    reference_price = "10"
    evidence_sha = hashlib.sha256(
        _evidence_preimage(
            asset_id="ASSETUSDT",
            binance_symbol="ASSETUSDT",
            binance_raw_sha256=binance_sha,
            okx_inst_id="ASSET-USDT",
            okx_raw_sha256=okx_sha,
            captured_at=CAPTURED,
            reference_price=reference_price,
        )
    ).hexdigest()
    evidence = {
        "schema": DB_EVIDENCE_SCHEMA,
        "source_id": DB_SOURCE_ID,
        "asset_id": "ASSETUSDT",
        "captured_at": CAPTURED.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "reference_price": reference_price,
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
                "price": "10",
                "observed_at": BINANCE_OBSERVED.isoformat().replace("+00:00", "Z"),
                "raw_response_sha256": binance_sha,
                "raw_response_utf8": binance_raw.decode(),
            },
            {
                "venue": "OKX_SPOT",
                "symbol": "ASSET-USDT",
                "price": "10",
                "observed_at": OKX_OBSERVED.isoformat().replace("+00:00", "Z"),
                "raw_response_sha256": okx_sha,
                "raw_response_utf8": okx_raw.decode(),
            },
        ],
    }
    return {
        "sequence": 9,
        "asset_id": "ASSETUSDT",
        "reference_price": reference_price,
        "observed_at": OKX_OBSERVED.isoformat(),
        "captured_at": CAPTURED.isoformat(),
        "created_at": CREATED.isoformat(),
        "source_id": DB_SOURCE_ID,
        "evidence_sha256": evidence_sha,
        "evidence": evidence,
    }


def test_db_fetched_reference_receipt_reproduces_from_retained_provider_bytes():
    receipt = reference_receipt_from_store_row(_valid_row())
    assert receipt.asset_id == "ASSETUSDT"
    assert receipt.reference_price == "10"
    assert receipt.observed_at == OKX_OBSERVED
    assert receipt.source_id == DB_SOURCE_ID
    assert receipt.observation_id == "big_move_reference:9"


def test_retained_provider_byte_tampering_is_rejected():
    row = _valid_row()
    row["evidence"]["providers"][0]["raw_response_utf8"] = row["evidence"]["providers"][0]["raw_response_utf8"].replace("10.00", "5.00")
    with pytest.raises(ValueError, match="Binance bytes SHA-256 mismatch"):
        reference_receipt_from_store_row(row)


def test_reference_price_tampering_is_rejected_even_with_original_raw_bytes():
    row = _valid_row()
    row["reference_price"] = "5"
    row["evidence"]["reference_price"] = "5"
    with pytest.raises(ValueError, match="does not reproduce from retained bytes|SHA-256 does not reproduce"):
        reference_receipt_from_store_row(row)


def test_caller_constructible_v1_capture_can_never_receive_authoritative_receipt():
    fake = TrustedReferenceCapture(
        asset_id="ASSETUSDT",
        captured_at=CAPTURED,
        reference_price="1",
        observed_at=CAPTURED,
        evidence={},
        evidence_sha256="0" * 64,
    )
    with pytest.raises(RuntimeError, match="cannot receive a trusted receipt"):
        persist_trusted_reference_capture(fake)


def test_authoritative_capture_api_accepts_identifiers_only():
    signature = inspect.signature(capture_and_persist_trusted_reference)
    assert set(signature.parameters) == {"binance_symbol", "okx_inst_id"}
    assert "price" not in signature.parameters
    assert "capture" not in signature.parameters
    assert "raw" not in signature.parameters

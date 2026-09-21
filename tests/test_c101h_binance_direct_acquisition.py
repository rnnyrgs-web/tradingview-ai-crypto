from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from c101h_binance_direct_acquisition import (
    CONTRACT_ID,
    _validate_provider_body,
    canonical_receipt,
    freeze_binance_c101h_request,
    load_contract,
)
from trusted_remote_acquisition import FetchResult


GOOD_CONTEXT = {
    "repository": "rnnyrgs-web/tradingview-ai-crypto",
    "git_sha": "a" * 40,
    "git_ref": "refs/heads/main",
    "workflow_ref": (
        "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
        "pit-trusted-remote-acquisition.yml@refs/heads/main"
    ),
    "run_id": 123,
    "run_attempt": 1,
    "event_name": "workflow_dispatch",
}


def _result(body: bytes) -> FetchResult:
    return FetchResult(
        status=200,
        headers={"content-type": "application/octet-stream"},
        body=body,
        started_at="2026-09-21T12:00:00Z",
        completed_at="2026-09-21T12:00:01Z",
    )


@pytest.mark.parametrize(
    "path",
    [
        "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip",
        "data/futures/um/monthly/klines/ETHUSDT/1h/ETHUSDT-1h-2025-12.zip",
        "data/futures/um/monthly/fundingRate/SOLUSDT/SOLUSDT-fundingRate-2026-08.zip",
    ],
)
def test_accepts_only_frozen_c101h_archive_families(path: str):
    request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_ARCHIVE", object_path=path
    )
    assert request.host == "data.binance.vision"
    assert request.url == "https://data.binance.vision/" + path
    assert request.range_header is None


@pytest.mark.parametrize(
    "path",
    [
        "data/spot/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip",
        "data/spot/monthly/klines/DOGEUSDT/1h/DOGEUSDT-1h-2026-08.zip",
        "data/futures/um/monthly/fundingRate/BTCUSDT/ETHUSDT-fundingRate-2026-08.zip",
        "data/spot/monthly/klines/BTCUSDT/1h/../BTCUSDT-1h-2026-08.zip",
        "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.csv",
        "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip?x=1",
    ],
)
def test_rejects_non_frozen_or_unsafe_archive_paths(path: str):
    with pytest.raises(ValueError):
        freeze_binance_c101h_request(
            source_kind="BINANCE_C101H_ARCHIVE", object_path=path
        )


@pytest.mark.parametrize("month", ["2026-09", "2026-10", "2027-01"])
def test_protected_months_fail_closed_before_fetch(month: str):
    path = f"data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{month}.zip"
    with pytest.raises(ValueError, match="protected"):
        freeze_binance_c101h_request(
            source_kind="BINANCE_C101H_ARCHIVE", object_path=path
        )


def test_checksum_must_be_exact_companion_and_declares_same_archive():
    archive = (
        "data/futures/um/monthly/fundingRate/BTCUSDT/"
        "BTCUSDT-fundingRate-2026-08.zip"
    )
    request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_CHECKSUM",
        object_path=archive + ".CHECKSUM",
    )
    digest = "a" * 64
    metadata = _validate_provider_body(
        request, f"{digest}  BTCUSDT-fundingRate-2026-08.zip\n".encode("ascii")
    )
    assert metadata["declared_archive_sha256"] == digest
    assert metadata["archive_filename"] == "BTCUSDT-fundingRate-2026-08.zip"

    with pytest.raises(ValueError, match="filename"):
        _validate_provider_body(
            request, f"{digest}  ETHUSDT-fundingRate-2026-08.zip\n".encode("ascii")
        )


def test_archive_response_must_be_zip_stream():
    request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_ARCHIVE",
        object_path="data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip",
    )
    assert (
        _validate_provider_body(request, b"PK\x03\x04payload")[
            "declared_archive_sha256"
        ]
        is None
    )
    with pytest.raises(ValueError, match="ZIP"):
        _validate_provider_body(request, b"not-a-zip")


def test_receipt_binds_provider_bytes_and_development_only_authority():
    request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_ARCHIVE",
        object_path="data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip",
    )
    result = _result(b"PK\x03\x04payload")
    metadata = _validate_provider_body(request, result.body)
    receipt = canonical_receipt(
        request, result, github_context=GOOD_CONTEXT, provider_metadata=metadata
    )
    assert receipt["source_contract_id"] == CONTRACT_ID
    assert receipt["response"]["sha256"] == hashlib.sha256(result.body).hexdigest()
    assert receipt["protected_evidence"] == "DEVELOPMENT_MONTHS_ONLY_THROUGH_2026_08"
    assert "broker" not in json.dumps(receipt).lower()


def test_frozen_contract_bytes_match_code_pin(tmp_path: Path):
    (tmp_path / "orchestration" / "data").mkdir(parents=True)
    source = (
        Path(__file__).resolve().parents[1]
        / "orchestration"
        / "data"
        / "c101h_binance_direct_acquisition_contract_v1.json"
    )
    target = tmp_path / "orchestration" / "data" / source.name
    target.write_bytes(source.read_bytes())
    assert load_contract(tmp_path)["artifact_id"] == CONTRACT_ID
    target.write_text(target.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_contract(tmp_path)

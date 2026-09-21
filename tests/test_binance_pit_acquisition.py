from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from binance_pit_acquisition import (
    TRUST_POLICY,
    build_acquisition_receipt,
    resolve_frozen_source,
)


def _write_valid_pair(tmp_path: Path, archive_name: str) -> tuple[Path, Path]:
    csv_name = archive_name.removesuffix(".zip") + ".csv"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(csv_name, b"1,2,3\n")
    archive_bytes = buffer.getvalue()
    archive = tmp_path / archive_name
    checksum = tmp_path / f"{archive_name}.CHECKSUM"
    archive.write_bytes(archive_bytes)
    checksum.write_text(
        f"{hashlib.sha256(archive_bytes).hexdigest()}  {archive_name}\n",
        encoding="utf-8",
    )
    return archive, checksum


def test_resolver_is_frozen_to_named_consumer_universe_and_development_period():
    request = resolve_frozen_source("usdm_funding_rate", "BTCUSDT", "2026-08")
    assert request.archive_url == (
        "https://data.binance.vision/data/futures/um/monthly/fundingRate/"
        "BTCUSDT/BTCUSDT-fundingRate-2026-08.zip"
    )
    assert request.checksum_url == request.archive_url + ".CHECKSUM"

    with pytest.raises(ValueError, match="outside frozen"):
        resolve_frozen_source("spot_kline", "XRPUSDT", "2026-08")
    with pytest.raises(ValueError, match="outside frozen C101-H development coverage"):
        resolve_frozen_source("spot_kline", "BTCUSDT", "2026-09")
    with pytest.raises(ValueError, match="outside frozen C101-H development coverage"):
        resolve_frozen_source("spot_kline", "BTCUSDT", "2023-06")


def test_receipt_requires_main_repo_identity_http_success_and_local_checksum(tmp_path):
    request = resolve_frozen_source("spot_kline", "BTCUSDT", "2025-01")
    archive, checksum = _write_valid_pair(tmp_path, request.archive_filename)
    receipt = build_acquisition_receipt(
        request,
        archive_path=archive,
        checksum_path=checksum,
        archive_http_status=200,
        archive_final_url=request.archive_url,
        checksum_http_status=200,
        checksum_final_url=request.checksum_url,
        captured_at_utc="2026-09-21T11:00:00+00:00",
        workflow_repository=TRUST_POLICY["repository"],
        workflow_ref=TRUST_POLICY["source_ref"],
        workflow_sha="a" * 40,
        workflow_run_id="123",
        workflow_run_attempt="1",
    )
    assert receipt["status"] == "FETCHED_AWAITING_ATTESTATION_VERIFICATION"
    assert receipt["data_ready_authority"] is False
    assert receipt["required_consumer_verification"]["signer_workflow"] == TRUST_POLICY["signer_workflow"]
    assert receipt["required_consumer_verification"]["source_ref"] == "refs/heads/main"
    assert receipt["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()

    kwargs = dict(
        request=request,
        archive_path=archive,
        checksum_path=checksum,
        archive_http_status=200,
        archive_final_url=request.archive_url,
        checksum_http_status=200,
        checksum_final_url=request.checksum_url,
        captured_at_utc="2026-09-21T11:00:00+00:00",
        workflow_repository=TRUST_POLICY["repository"],
        workflow_ref=TRUST_POLICY["source_ref"],
        workflow_sha="b" * 40,
        workflow_run_id="123",
        workflow_run_attempt="1",
    )
    kwargs["workflow_ref"] = "refs/heads/untrusted-branch"
    with pytest.raises(ValueError, match="refs/heads/main"):
        build_acquisition_receipt(**kwargs)

    kwargs["workflow_ref"] = TRUST_POLICY["source_ref"]
    kwargs["archive_http_status"] = 404
    with pytest.raises(ValueError, match="HTTP 200"):
        build_acquisition_receipt(**kwargs)


def test_matching_fabricated_local_pair_never_claims_data_ready(tmp_path):
    """Local consistency is deliberately weaker than server-attested provenance."""
    request = resolve_frozen_source("usdm_perp_kline", "ETHUSDT", "2024-02")
    archive, checksum = _write_valid_pair(tmp_path, request.archive_filename)
    receipt = build_acquisition_receipt(
        request,
        archive_path=archive,
        checksum_path=checksum,
        archive_http_status=200,
        archive_final_url=request.archive_url,
        checksum_http_status=200,
        checksum_final_url=request.checksum_url,
        captured_at_utc="2026-09-21T11:00:00+00:00",
        workflow_repository=TRUST_POLICY["repository"],
        workflow_ref=TRUST_POLICY["source_ref"],
        workflow_sha="c" * 40,
        workflow_run_id="999",
        workflow_run_attempt="1",
    )
    assert receipt["data_ready_authority"] is False
    assert receipt["status"] == "FETCHED_AWAITING_ATTESTATION_VERIFICATION"
    assert receipt["required_consumer_verification"]["tool"] == "gh attestation verify"

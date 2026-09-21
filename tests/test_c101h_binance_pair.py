from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

import c101h_binance_direct_consumer as direct_consumer
from c101h_binance_direct_acquisition import (
    freeze_binance_c101h_request,
    write_bundle,
)
from c101h_binance_pair import verify_attested_c101h_archive_checksum_pair
from trusted_remote_acquisition import (
    EXPECTED_EVENT,
    EXPECTED_REF,
    EXPECTED_REPOSITORY,
    EXPECTED_WORKFLOW_REF,
    FetchResult,
)


def _context() -> dict:
    return {
        "repository": EXPECTED_REPOSITORY,
        "git_sha": "a" * 40,
        "git_ref": EXPECTED_REF,
        "workflow_ref": EXPECTED_WORKFLOW_REF,
        "run_id": 123,
        "run_attempt": 1,
        "event_name": EXPECTED_EVENT,
    }


def _result(body: bytes) -> FetchResult:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return FetchResult(
        status=200,
        headers={"content-type": "application/octet-stream"},
        body=body,
        started_at=now,
        completed_at=now,
    )


def _pair(tmp_path: Path, *, declared_sha: str | None = None) -> tuple[Path, Path, bytes]:
    object_path = "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip"
    archive_bytes = b"PK\x03\x04provider-archive-bytes"
    actual_sha = hashlib.sha256(archive_bytes).hexdigest()
    checksum_sha = declared_sha or actual_sha

    archive_request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_ARCHIVE", object_path=object_path
    )
    checksum_request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_CHECKSUM", object_path=object_path + ".CHECKSUM"
    )
    archive_written = write_bundle(
        archive_request,
        _result(archive_bytes),
        output_dir=tmp_path / "archive",
        github_context=_context(),
    )
    checksum_written = write_bundle(
        checksum_request,
        _result(f"{checksum_sha}  BTCUSDT-1h-2026-08.zip\n".encode("ascii")),
        output_dir=tmp_path / "checksum",
        github_context=_context(),
    )
    return (
        Path(archive_written["bundle_path"]),
        Path(checksum_written["bundle_path"]),
        archive_bytes,
    )


def test_pair_requires_two_valid_attestations_and_matching_provider_checksum(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        direct_consumer,
        "_verify_github_attestation",
        lambda path: calls.append(path),
    )
    archive_bundle, checksum_bundle, expected = _pair(tmp_path)
    archive_receipt, checksum_receipt, raw = verify_attested_c101h_archive_checksum_pair(
        archive_bundle, checksum_bundle
    )
    assert raw == expected
    assert len(calls) == 2
    assert (
        checksum_receipt["provider_metadata"]["declared_archive_sha256"]
        == archive_receipt["response"]["sha256"]
    )


def test_pair_rejects_authenticated_checksum_that_does_not_match_archive(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        direct_consumer,
        "_verify_github_attestation",
        lambda path: None,
    )
    archive_bundle, checksum_bundle, _ = _pair(tmp_path, declared_sha="b" * 64)
    with pytest.raises(ValueError, match="checksum does not match"):
        verify_attested_c101h_archive_checksum_pair(archive_bundle, checksum_bundle)

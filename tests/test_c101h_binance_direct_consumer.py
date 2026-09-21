from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest

import c101h_binance_direct_consumer as consumer
from c101h_binance_direct_acquisition import (
    freeze_binance_c101h_request,
    write_bundle,
)
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


def _bundle(tmp_path: Path, *, kind: str = "BINANCE_C101H_ARCHIVE") -> Path:
    archive_path = "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-08.zip"
    object_path = (
        archive_path if kind == "BINANCE_C101H_ARCHIVE" else archive_path + ".CHECKSUM"
    )
    request = freeze_binance_c101h_request(source_kind=kind, object_path=object_path)
    body = (
        b"PK\x03\x04provider-zip"
        if kind == "BINANCE_C101H_ARCHIVE"
        else (("a" * 64 + "  BTCUSDT-1h-2026-08.zip\n").encode("ascii"))
    )
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = FetchResult(
        status=200,
        headers={"content-type": "application/octet-stream"},
        body=body,
        started_at=now,
        completed_at=now,
    )
    written = write_bundle(
        request, result, output_dir=tmp_path, github_context=_context()
    )
    return Path(written["bundle_path"])


def _allow_attestation(monkeypatch, calls):
    monkeypatch.setattr(consumer.shutil, "which", lambda name: "/usr/bin/gh")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="verified", stderr="")

    monkeypatch.setattr(consumer.subprocess, "run", fake_run)


@pytest.mark.parametrize(
    "kind", ["BINANCE_C101H_ARCHIVE", "BINANCE_C101H_CHECKSUM"]
)
def test_attested_c101h_bundle_verifies_exact_source_kind(tmp_path, monkeypatch, kind):
    bundle = _bundle(tmp_path, kind=kind)
    calls = []
    _allow_attestation(monkeypatch, calls)
    receipt, response = consumer.verify_attested_c101h_bundle(
        bundle, expected_source_kind=kind
    )
    assert receipt["source_kind"] == kind
    assert response
    command = calls[0][0]
    assert command[:3] == ["/usr/bin/gh", "attestation", "verify"]
    assert "--signer-workflow" in command
    assert "--source-ref" in command


def test_missing_or_failed_attestation_never_falls_back_to_local_receipt(
    tmp_path, monkeypatch
):
    bundle = _bundle(tmp_path)
    monkeypatch.setattr(consumer.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="GitHub CLI is required"):
        consumer.verify_attested_c101h_bundle(
            bundle, expected_source_kind="BINANCE_C101H_ARCHIVE"
        )

    monkeypatch.setattr(consumer.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        consumer.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="no attestation"
        ),
    )
    with pytest.raises(ValueError, match="attestation did not verify"):
        consumer.verify_attested_c101h_bundle(
            bundle, expected_source_kind="BINANCE_C101H_ARCHIVE"
        )


def test_tampered_response_fails_even_when_attestation_mocked_green(
    tmp_path, monkeypatch
):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    with tarfile.open(bundle, "r:") as archive:
        receipt_raw = archive.extractfile("receipt.json").read()
    with tarfile.open(bundle, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, raw in (
            ("receipt.json", receipt_raw),
            ("response.bin", b"PK\x03\x04tampered"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.uid = info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))
    with pytest.raises(ValueError, match="response bytes do not match"):
        consumer.verify_attested_c101h_bundle(
            bundle, expected_source_kind="BINANCE_C101H_ARCHIVE"
        )


def test_wrong_source_kind_and_extra_bundle_members_fail_closed(
    tmp_path, monkeypatch
):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    with pytest.raises(ValueError, match="source kind mismatch"):
        consumer.verify_attested_c101h_bundle(
            bundle, expected_source_kind="BINANCE_C101H_CHECKSUM"
        )

    bundle = _bundle(tmp_path / "extra")
    with tarfile.open(bundle, "r:") as archive:
        receipt_raw = archive.extractfile("receipt.json").read()
        response_raw = archive.extractfile("response.bin").read()
    with tarfile.open(bundle, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, raw in (
            ("receipt.json", receipt_raw),
            ("response.bin", response_raw),
            ("extra.txt", b"x"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    with pytest.raises(ValueError, match="exactly receipt.json and response.bin"):
        consumer.verify_attested_c101h_bundle(
            bundle, expected_source_kind="BINANCE_C101H_ARCHIVE"
        )

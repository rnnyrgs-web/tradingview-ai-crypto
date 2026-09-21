from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest

import trusted_remote_acquisition_consumer as consumer
from trusted_remote_acquisition import (
    FetchResult,
    EXPECTED_REPOSITORY,
    EXPECTED_REF,
    EXPECTED_WORKFLOW_PATH,
    EXPECTED_WORKFLOW_REF,
    freeze_binance_listobjects_request,
    write_bundle,
)


def _context():
    return {
        "repository": EXPECTED_REPOSITORY,
        "git_sha": "a" * 40,
        "git_ref": EXPECTED_REF,
        "workflow_ref": EXPECTED_WORKFLOW_REF,
        "run_id": 123,
        "run_attempt": 1,
        "event_name": "workflow_dispatch",
    }


def _bundle(tmp_path: Path) -> Path:
    request = freeze_binance_listobjects_request(prefix="data/spot/monthly/klines/")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = FetchResult(
        status=200,
        headers={"content-type": "application/xml"},
        body=b"<ListBucketResult/>",
        started_at=now,
        completed_at=now,
    )
    written = write_bundle(request, result, output_dir=tmp_path, github_context=_context())
    return Path(written["bundle_path"])


def _allow_attestation(monkeypatch, calls):
    monkeypatch.setattr(consumer.shutil, "which", lambda name: "/usr/bin/gh")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="verified", stderr="")

    monkeypatch.setattr(consumer.subprocess, "run", fake_run)


def test_missing_github_cli_fails_closed_before_local_receipt_can_gain_authority(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    monkeypatch.setattr(consumer.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="GitHub CLI is required"):
        consumer.verify_attested_acquisition_bundle(
            bundle, expected_source_kind="BINANCE_LISTOBJECTS_V2"
        )


def test_attestation_command_pins_repo_signer_workflow_and_source_ref(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    receipt, response = consumer.verify_attested_acquisition_bundle(
        bundle, expected_source_kind="BINANCE_LISTOBJECTS_V2"
    )
    assert response == b"<ListBucketResult/>"
    assert receipt["source_kind"] == "BINANCE_LISTOBJECTS_V2"
    command = calls[0][0]
    assert command[:3] == ["/usr/bin/gh", "attestation", "verify"]
    assert command[command.index("--repo") + 1] == EXPECTED_REPOSITORY
    assert command[command.index("--signer-workflow") + 1] == f"{EXPECTED_REPOSITORY}/{EXPECTED_WORKFLOW_PATH}"
    assert command[command.index("--source-ref") + 1] == EXPECTED_REF
    assert calls[0][1]["timeout"] == 120


def test_failed_github_attestation_never_falls_back_to_local_hashes(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    monkeypatch.setattr(consumer.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        consumer.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="no attestation"),
    )
    with pytest.raises(ValueError, match="attestation did not verify"):
        consumer.verify_attested_acquisition_bundle(
            bundle, expected_source_kind="BINANCE_LISTOBJECTS_V2"
        )


def test_tampered_response_is_rejected_even_if_external_verifier_is_mocked_green(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    with tarfile.open(bundle, "r:") as archive:
        receipt_raw = archive.extractfile("receipt.json").read()
    with tarfile.open(bundle, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, raw in (
            ("receipt.json", receipt_raw),
            ("response.bin", b"tampered-provider-bytes"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.uid = info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))
    with pytest.raises(ValueError, match="response bytes do not match trusted receipt"):
        consumer.verify_attested_acquisition_bundle(
            bundle, expected_source_kind="BINANCE_LISTOBJECTS_V2"
        )


def test_wrong_source_kind_is_rejected_after_valid_receipt_verification(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    with pytest.raises(ValueError, match="source kind mismatch"):
        consumer.verify_attested_acquisition_bundle(
            bundle, expected_source_kind="COMMONCRAWL_INDEX"
        )


def test_extra_or_link_members_are_rejected(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    calls = []
    _allow_attestation(monkeypatch, calls)
    with tarfile.open(bundle, "r:") as archive:
        receipt_raw = archive.extractfile("receipt.json").read()
        response_raw = archive.extractfile("response.bin").read()
    with tarfile.open(bundle, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, raw in (("receipt.json", receipt_raw), ("response.bin", response_raw), ("extra.txt", b"x")):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    with pytest.raises(ValueError, match="exactly receipt.json and response.bin"):
        consumer.verify_attested_acquisition_bundle(
            bundle, expected_source_kind="BINANCE_LISTOBJECTS_V2"
        )

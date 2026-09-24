from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

import kraken_eth_session_direct_acquisition as acquisition


def _fake_github_context() -> dict:
    return {
        "repository": "rnnyrgs-web/tradingview-ai-crypto",
        "git_sha": "a" * 40,
        "git_ref": "refs/heads/main",
        "workflow_ref": (
            "rnnyrgs-web/tradingview-ai-crypto/"
            ".github/workflows/pit-trusted-remote-acquisition.yml@refs/heads/main"
        ),
        "run_id": 123,
        "run_attempt": 1,
        "event_name": "workflow_dispatch",
    }


def _write_zip(path: Path, *, manifest: bytes = b'{"build":"test"}') -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", manifest)
        archive.writestr("ETHUSD_60.csv", "1767229200,1,2,0.5,1.5,10,3\n")


def test_contract_is_exactly_bound_to_frozen_replication() -> None:
    contract = acquisition.load_contract()
    assert contract["replication_id"] == acquisition.CONTRACT_ID
    assert contract["artifact_sha256"] == acquisition.CONTRACT_ARTIFACT_SHA256
    assert contract["data_contract"]["required_incremental_archives"] == list(
        acquisition.SOURCE_URLS.values()
    )
    assert contract["data_contract"]["screen_may_read_protected_shadow"] is False
    assert contract["screening_authority"]["screen_started"] is False
    assert contract["screening_authority"]["trade_authority"] is False
    assert contract["execution_rules"]["broker_connected"] is False
    assert contract["execution_rules"]["live_trading"] is False


def test_only_two_exact_kraken_archives_are_authorized() -> None:
    q1 = acquisition.freeze_kraken_request(
        source_kind="KRAKEN_ETH_SESSION_2026Q1_ARCHIVE"
    )
    q2 = acquisition.freeze_kraken_request(
        source_kind="KRAKEN_ETH_SESSION_2026Q2_ARCHIVE"
    )
    assert q1.url == acquisition.SOURCE_URLS[q1.source_kind]
    assert q2.url == acquisition.SOURCE_URLS[q2.source_kind]
    assert q1.host == q2.host == "assets.kraken.com"
    assert q1.target == "/marketing/institutions/Kraken_OHLCVT_2026Q1.zip"
    assert q2.target == "/marketing/institutions/Kraken_OHLCVT_2026Q2.zip"
    with pytest.raises(ValueError, match="unsupported"):
        acquisition.freeze_kraken_request(source_kind="KRAKEN_ARBITRARY_ARCHIVE")


def test_archive_validation_binds_exact_root_manifest(tmp_path: Path) -> None:
    archive_path = tmp_path / "q1.zip"
    manifest = b'{"build":"2026Q1","files":["ETHUSD_60.csv"]}'
    _write_zip(archive_path, manifest=manifest)

    metadata = acquisition.validate_archive(archive_path)
    assert metadata["manifest_bytes"] == manifest
    assert metadata["manifest_sha256"] == hashlib.sha256(manifest).hexdigest()
    assert metadata["manifest_byte_count"] == len(manifest)
    assert metadata["zip_member_count"] == 2


def test_archive_without_root_manifest_fails_closed(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/MANIFEST.json", "{}")
        archive.writestr("ETHUSD_60.csv", "x")
    with pytest.raises(ValueError, match="exactly one root MANIFEST"):
        acquisition.validate_archive(archive_path)


def test_duplicate_manifest_fails_closed(tmp_path: Path) -> None:
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("MANIFEST.json", "{}")
        archive.writestr("MANIFEST.json", "{}")
    with pytest.raises(ValueError, match="exactly one root MANIFEST"):
        acquisition.validate_archive(archive_path)


def test_manifest_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    archive_path = tmp_path / "duplicate-keys.zip"
    _write_zip(archive_path, manifest=b'{"files":[],"files":[]}')
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        acquisition.validate_archive(archive_path)


def test_content_length_is_bounded_and_exact_when_present() -> None:
    assert acquisition._parse_content_length({"content-length": "123"}, maximum=200) == 123
    assert acquisition._parse_content_length({}, maximum=200) is None
    with pytest.raises(ValueError, match="positive"):
        acquisition._parse_content_length({"content-length": "0"}, maximum=200)
    with pytest.raises(ValueError, match="frozen byte limit"):
        acquisition._parse_content_length({"content-length": "201"}, maximum=200)
    with pytest.raises(ValueError, match="nonnegative integer"):
        acquisition._parse_content_length({"content-length": "1.5"}, maximum=200)


def test_receipt_never_grants_screen_or_trading_authority() -> None:
    request = acquisition.freeze_kraken_request(
        source_kind="KRAKEN_ETH_SESSION_2026Q1_ARCHIVE"
    )
    result = acquisition.StreamFetchResult(
        status=200,
        headers={"content-type": "application/zip", "etag": '"abc"'},
        response_sha256="b" * 64,
        byte_count=1234,
        started_at="2026-09-24T00:00:00Z",
        completed_at="2026-09-24T00:01:00Z",
    )
    metadata = {
        "manifest_sha256": "c" * 64,
        "manifest_byte_count": 42,
        "zip_member_count": 10,
    }
    receipt = acquisition.canonical_receipt(
        request,
        result,
        github_context=_fake_github_context(),
        source_contract_bytes_sha256="d" * 64,
        archive_metadata=metadata,
    )
    authority = receipt["scientific_authority"]
    assert authority["archive_provenance_possible_after_attestation"] is True
    assert authority["manifest_provenance_possible_after_attestation"] is True
    assert authority["pair_resolution_authority"] is False
    assert authority["timestamp_semantics_authority"] is False
    assert authority["normalized_rows_authority"] is False
    assert authority["strategy_screen_authority"] is False
    assert authority["protected_shadow_authority"] is False
    assert authority["profitability_claim_authority"] is False
    assert authority["promotion_authority"] is False
    assert authority["broker_connected"] is False
    assert authority["live_trading"] is False

    unsigned = dict(receipt)
    stored = unsigned.pop("receipt_sha256")
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert stored == hashlib.sha256(canonical).hexdigest()


def test_bundle_contains_exact_archive_manifest_and_receipt(tmp_path: Path) -> None:
    response = tmp_path / "response.bin"
    _write_zip(response)
    manifest = acquisition.validate_archive(response)["manifest_bytes"]
    receipt = {"schema": "test", "receipt_sha256": "e" * 64}

    written = acquisition.write_bundle(
        response,
        manifest,
        receipt,
        output_dir=tmp_path / "out",
    )
    bundle = Path(written["bundle_path"])
    assert written["bundle_sha256"] == acquisition._file_sha256(bundle)
    with __import__("tarfile").open(bundle, "r") as archive:
        assert archive.getnames() == ["receipt.json", "MANIFEST.json", "response.bin"]
        assert archive.extractfile("response.bin").read() == response.read_bytes()
        assert archive.extractfile("MANIFEST.json").read() == manifest

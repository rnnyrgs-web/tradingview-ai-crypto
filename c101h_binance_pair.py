"""Pair attested C101-H Binance archives with their exact provider checksums."""

from __future__ import annotations

from pathlib import Path

from c101h_binance_direct_consumer import verify_attested_c101h_bundle


def verify_attested_c101h_archive_checksum_pair(
    archive_bundle: str | Path,
    checksum_bundle: str | Path,
) -> tuple[dict, dict, bytes]:
    """Verify both attestations and prove the provider checksum binds the archive bytes."""
    archive_receipt, archive_bytes = verify_attested_c101h_bundle(
        archive_bundle, expected_source_kind="BINANCE_C101H_ARCHIVE"
    )
    checksum_receipt, _ = verify_attested_c101h_bundle(
        checksum_bundle, expected_source_kind="BINANCE_C101H_CHECKSUM"
    )

    archive_request = archive_receipt.get("request")
    checksum_request = checksum_receipt.get("request")
    if not isinstance(archive_request, dict) or not isinstance(checksum_request, dict):
        raise ValueError("C101-H pair request blocks missing")
    archive_url = archive_request.get("url")
    checksum_url = checksum_request.get("url")
    if not isinstance(archive_url, str) or checksum_url != archive_url + ".CHECKSUM":
        raise ValueError("C101-H checksum is not the exact companion of the archive")

    archive_meta = archive_receipt.get("provider_metadata")
    checksum_meta = checksum_receipt.get("provider_metadata")
    if not isinstance(archive_meta, dict) or not isinstance(checksum_meta, dict):
        raise ValueError("C101-H pair provider metadata missing")
    if archive_meta.get("archive_filename") != checksum_meta.get("archive_filename"):
        raise ValueError("C101-H checksum filename does not bind the archive")
    declared = checksum_meta.get("declared_archive_sha256")
    actual = archive_receipt.get("response", {}).get("sha256")
    if not isinstance(declared, str) or declared != actual:
        raise ValueError("C101-H provider checksum does not match authenticated archive bytes")

    return archive_receipt, checksum_receipt, archive_bytes

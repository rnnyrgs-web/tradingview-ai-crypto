"""Fail-closed consumer verifier for trusted PIT remote-acquisition bundles.

The acquisition workflow in ``trusted_remote_acquisition.py`` creates deterministic
``trusted-acquisition.tar`` subjects, but the tar/receipt is not authoritative merely
because it exists locally.  This module verifies the GitHub Artifact Attestation for
that exact subject using the frozen repository + signer workflow + source-ref, then
extracts only the two expected regular files and re-verifies the receipt against the
response bytes.

The helper is deliberately narrow and grants provider-byte provenance only.  It does
not grant universe, label, candidate, strategy, promotion, broker or trade authority.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess  # nosec B404 -- fixed gh executable + fixed argv; shell is never used
import tarfile
from typing import Any

from trusted_remote_acquisition import (
    EXPECTED_EVENT,
    EXPECTED_REF,
    EXPECTED_REPOSITORY,
    EXPECTED_WORKFLOW_PATH,
    EXPECTED_WORKFLOW_REF,
    MAX_BINANCE_BYTES,
    MAX_CC_INDEX_BYTES,
    MAX_CC_WARC_BYTES,
    verify_receipt_bytes,
)

EXPECTED_MEMBERS = {"receipt.json", "response.bin"}
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = MAX_CC_WARC_BYTES + MAX_RECEIPT_BYTES + 2 * 1024 * 1024
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _gh_binary() -> str:
    executable = shutil.which("gh")
    if not executable:
        raise ValueError("GitHub CLI is required for artifact-attestation verification")
    return executable


def _verify_github_attestation(bundle: Path) -> None:
    command = [
        _gh_binary(),
        "attestation",
        "verify",
        str(bundle),
        "--repo",
        EXPECTED_REPOSITORY,
        "--signer-workflow",
        f"{EXPECTED_REPOSITORY}/{EXPECTED_WORKFLOW_PATH}",
        "--source-ref",
        EXPECTED_REF,
    ]
    try:
        # Security boundary: executable is resolved by shutil.which, every option is
        # a frozen constant except the already-resolved bundle path, argv is passed
        # as a sequence, and shell execution is never enabled.
        completed = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("GitHub artifact-attestation verification could not run") from exc
    if completed.returncode != 0:
        raise ValueError("GitHub artifact attestation did not verify for trusted signer")


def _read_exact_members(bundle: Path) -> tuple[dict[str, Any], bytes]:
    try:
        size = bundle.stat().st_size
    except OSError as exc:
        raise ValueError("trusted acquisition bundle is unavailable") from exc
    if size <= 0 or size > MAX_BUNDLE_BYTES:
        raise ValueError("trusted acquisition bundle size is outside frozen bound")

    try:
        with tarfile.open(bundle, "r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if set(names) != EXPECTED_MEMBERS or len(names) != len(EXPECTED_MEMBERS):
                raise ValueError("trusted acquisition bundle must contain exactly receipt.json and response.bin")
            payloads: dict[str, bytes] = {}
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or len(name.parts) != 1:
                    raise ValueError("trusted acquisition bundle member path is unsafe")
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError("trusted acquisition bundle members must be regular files")
                if member.name == "receipt.json" and member.size > MAX_RECEIPT_BYTES:
                    raise ValueError("trusted acquisition receipt exceeds frozen size bound")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("trusted acquisition bundle member cannot be read")
                raw = extracted.read()
                if len(raw) != member.size:
                    raise ValueError("trusted acquisition bundle member size mismatch")
                payloads[member.name] = raw
    except (tarfile.TarError, OSError) as exc:
        raise ValueError("trusted acquisition bundle is not a valid deterministic tar") from exc

    try:
        receipt = json.loads(payloads["receipt.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("trusted acquisition receipt is malformed") from exc
    if not isinstance(receipt, dict):
        raise ValueError("trusted acquisition receipt must be an object")
    return receipt, payloads["response.bin"]


def verify_attested_acquisition_bundle(
    bundle_path: str | Path,
    *,
    expected_source_kind: str,
) -> tuple[dict[str, Any], bytes]:
    """Verify attestation + exact receipt/bytes and return authenticated provider bytes.

    A missing ``gh`` verifier, failed attestation, unexpected signer/runtime identity,
    malformed tar, receipt mismatch or source-kind mismatch fails closed.
    """
    bundle = Path(bundle_path).resolve()
    _verify_github_attestation(bundle)
    receipt, response_bytes = _read_exact_members(bundle)
    verify_receipt_bytes(receipt, response_bytes)

    if receipt.get("source_kind") != expected_source_kind:
        raise ValueError("trusted acquisition receipt source kind mismatch")

    acquisition = receipt.get("acquisition")
    if not isinstance(acquisition, dict):
        raise ValueError("trusted acquisition receipt acquisition block missing")
    if acquisition.get("repository") != EXPECTED_REPOSITORY:
        raise ValueError("trusted acquisition receipt repository mismatch")
    if acquisition.get("git_ref") != EXPECTED_REF:
        raise ValueError("trusted acquisition receipt source ref mismatch")
    if acquisition.get("workflow_ref") != EXPECTED_WORKFLOW_REF:
        raise ValueError("trusted acquisition receipt signer workflow mismatch")
    if acquisition.get("event_name") != EXPECTED_EVENT:
        raise ValueError("trusted acquisition receipt event mismatch")
    git_sha = acquisition.get("git_sha")
    if not isinstance(git_sha, str) or not FULL_SHA_RE.fullmatch(git_sha):
        raise ValueError("trusted acquisition receipt git SHA is malformed")
    for field in ("run_id", "run_attempt"):
        value = acquisition.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"trusted acquisition receipt {field} must be a positive integer")

    response = receipt.get("response")
    if not isinstance(response, dict):
        raise ValueError("trusted acquisition receipt response block missing")
    byte_count = response.get("byte_count")
    if expected_source_kind in {"BINANCE_LISTOBJECTS_V2", "COMMONCRAWL_INDEX"}:
        if response.get("status") != 200 or not isinstance(byte_count, int) or byte_count > MAX_BINANCE_BYTES:
            raise ValueError("trusted non-range acquisition response violates frozen status/size")
    elif expected_source_kind == "COMMONCRAWL_WARC_RANGE":
        if response.get("status") != 206 or not isinstance(byte_count, int) or byte_count > MAX_CC_WARC_BYTES:
            raise ValueError("trusted WARC acquisition response violates frozen status/size")
    else:
        raise ValueError("unsupported trusted acquisition source kind")

    return receipt, response_bytes

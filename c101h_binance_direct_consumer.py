"""Fail-closed consumer for attested C101-H Binance direct-object bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess  # nosec B404 -- fixed gh executable + argv, no shell
import tarfile
from urllib.parse import urlsplit

from c101h_binance_direct_acquisition import (
    CONTRACT_ID,
    MAX_ARCHIVE_BYTES,
    MAX_CHECKSUM_BYTES,
    _validate_provider_body,
    freeze_binance_c101h_request,
)
from trusted_remote_acquisition import (
    EXPECTED_EVENT,
    EXPECTED_REF,
    EXPECTED_REPOSITORY,
    EXPECTED_WORKFLOW_PATH,
    EXPECTED_WORKFLOW_REF,
)

EXPECTED_MEMBERS = {"receipt.json", "response.bin"}
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = MAX_ARCHIVE_BYTES + MAX_RECEIPT_BYTES + 2 * 1024 * 1024


def _gh_binary() -> str:
    executable = shutil.which("gh")
    if not executable:
        raise ValueError("GitHub CLI is required for C101-H artifact-attestation verification")
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
        completed = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("C101-H GitHub artifact-attestation verification could not run") from exc
    if completed.returncode != 0:
        raise ValueError("C101-H GitHub artifact attestation did not verify for trusted signer")


def _read_exact_members(bundle: Path) -> tuple[dict, bytes]:
    try:
        size = bundle.stat().st_size
    except OSError as exc:
        raise ValueError("C101-H trusted acquisition bundle is unavailable") from exc
    if size <= 0 or size > MAX_BUNDLE_BYTES:
        raise ValueError("C101-H trusted acquisition bundle size is outside frozen bound")
    try:
        with tarfile.open(bundle, "r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if set(names) != EXPECTED_MEMBERS or len(names) != len(EXPECTED_MEMBERS):
                raise ValueError(
                    "C101-H bundle must contain exactly receipt.json and response.bin"
                )
            payloads: dict[str, bytes] = {}
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or len(name.parts) != 1:
                    raise ValueError("C101-H bundle member path is unsafe")
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError("C101-H bundle members must be regular files")
                if member.name == "receipt.json" and member.size > MAX_RECEIPT_BYTES:
                    raise ValueError("C101-H receipt exceeds frozen size bound")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("C101-H bundle member cannot be read")
                raw = extracted.read()
                if len(raw) != member.size:
                    raise ValueError("C101-H bundle member size mismatch")
                payloads[member.name] = raw
    except (tarfile.TarError, OSError) as exc:
        raise ValueError("C101-H bundle is not a valid deterministic tar") from exc
    try:
        receipt = json.loads(payloads["receipt.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("C101-H receipt is malformed") from exc
    if not isinstance(receipt, dict):
        raise ValueError("C101-H receipt must be an object")
    return receipt, payloads["response.bin"]


def _verify_receipt(receipt: dict, response_bytes: bytes, *, expected_source_kind: str) -> None:
    if receipt.get("schema") != "c101h_binance_direct_acquisition_receipt.v1":
        raise ValueError("unexpected C101-H receipt schema")
    if receipt.get("source_contract_id") != CONTRACT_ID:
        raise ValueError("unexpected C101-H acquisition contract")
    if receipt.get("source_kind") != expected_source_kind:
        raise ValueError("C101-H source kind mismatch")
    if receipt.get("consumer") != "#529 C101-H delta-neutral funding carry":
        raise ValueError("C101-H receipt consumer mismatch")
    if receipt.get("protected_evidence") != "DEVELOPMENT_MONTHS_ONLY_THROUGH_2026_08":
        raise ValueError("C101-H protected-evidence marker mismatch")

    response = receipt.get("response")
    if not isinstance(response, dict):
        raise ValueError("C101-H response block missing")
    if response.get("status") != 200:
        raise ValueError("C101-H direct object must have HTTP 200")
    if response.get("sha256") != hashlib.sha256(response_bytes).hexdigest():
        raise ValueError("C101-H response bytes do not match trusted receipt")
    if response.get("byte_count") != len(response_bytes):
        raise ValueError("C101-H response byte count mismatch")
    limit = (
        MAX_ARCHIVE_BYTES
        if expected_source_kind == "BINANCE_C101H_ARCHIVE"
        else MAX_CHECKSUM_BYTES
    )
    if len(response_bytes) > limit:
        raise ValueError("C101-H response exceeds frozen source-kind byte limit")

    request = receipt.get("request")
    if not isinstance(request, dict) or request.get("method") != "GET":
        raise ValueError("C101-H request block invalid")
    if request.get("range_header") is not None:
        raise ValueError("C101-H direct object must not use Range")
    url = request.get("url")
    if not isinstance(url, str):
        raise ValueError("C101-H request URL missing")
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname != "data.binance.vision"
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("C101-H request URL is outside frozen Binance host/path shape")
    object_path = parts.path.removeprefix("/")
    rebuilt = freeze_binance_c101h_request(
        source_kind=expected_source_kind, object_path=object_path
    )
    if rebuilt.url != url:
        raise ValueError("C101-H request URL does not match frozen canonical request")

    provider_metadata = _validate_provider_body(rebuilt, response_bytes)
    if receipt.get("provider_metadata") != provider_metadata:
        raise ValueError("C101-H provider metadata does not match authenticated bytes")

    acquisition = receipt.get("acquisition")
    if not isinstance(acquisition, dict):
        raise ValueError("C101-H acquisition block missing")
    expected_context = {
        "repository": EXPECTED_REPOSITORY,
        "git_ref": EXPECTED_REF,
        "workflow_ref": EXPECTED_WORKFLOW_REF,
        "event_name": EXPECTED_EVENT,
    }
    for key, expected in expected_context.items():
        if acquisition.get(key) != expected:
            raise ValueError(f"C101-H acquisition {key} mismatch")
    git_sha = acquisition.get("git_sha")
    if not isinstance(git_sha, str) or len(git_sha) != 40 or any(
        c not in "0123456789abcdef" for c in git_sha
    ):
        raise ValueError("C101-H acquisition git SHA is malformed")
    for field in ("run_id", "run_attempt"):
        value = acquisition.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"C101-H acquisition {field} must be a positive integer")

    stored = receipt.get("receipt_sha256")
    if (
        not isinstance(stored, str)
        or len(stored) != 64
        or any(c not in "0123456789abcdef" for c in stored)
    ):
        raise ValueError("C101-H receipt fingerprint malformed")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != stored:
        raise ValueError("C101-H receipt fingerprint mismatch")


def verify_attested_c101h_bundle(
    bundle_path: str | Path, *, expected_source_kind: str
) -> tuple[dict, bytes]:
    if expected_source_kind not in {
        "BINANCE_C101H_ARCHIVE",
        "BINANCE_C101H_CHECKSUM",
    }:
        raise ValueError("unsupported C101-H source kind")
    bundle = Path(bundle_path).resolve()
    _verify_github_attestation(bundle)
    receipt, response_bytes = _read_exact_members(bundle)
    _verify_receipt(
        receipt, response_bytes, expected_source_kind=expected_source_kind
    )
    return receipt, response_bytes

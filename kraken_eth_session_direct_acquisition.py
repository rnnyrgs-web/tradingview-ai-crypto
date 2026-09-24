"""Trusted direct Kraken OHLCVT acquisition for EXT-ETH-SESSION-REVERSAL-001-v1.

This helper authorizes only the two official Kraken incremental OHLCVT archives frozen
by the external-replication predeclaration.  It deliberately does *not* interpret
strategy outcomes, resolve the ETH/USD member, normalize rows, or grant any screening,
promotion, broker, or trading authority.

Provider bytes become scientific provenance only after the emitted bundle has a valid
GitHub artifact attestation for this repository and downstream deterministic preflight
verifies the archive/MANIFEST/pair/timestamp contract.  The helper streams large ZIPs
to disk instead of loading them into memory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import ssl
import tarfile
from typing import Any
import zipfile

from trusted_remote_acquisition import trusted_github_context


CONTRACT_PATH = "orchestration/external_replication/ext_eth_session_reversal_001_v1.json"
CONTRACT_ID = "EXT-ETH-SESSION-REVERSAL-001-v1"
CONTRACT_ARTIFACT_SHA256 = "6b8b71a5508fb61823f823e4596b644c29b6e4146175a2cd53cbd99f3976471a"
HOST = "assets.kraken.com"
SOURCE_URLS = {
    "KRAKEN_ETH_SESSION_2026Q1_ARCHIVE": (
        "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q1.zip"
    ),
    "KRAKEN_ETH_SESSION_2026Q2_ARCHIVE": (
        "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q2.zip"
    ),
}
MAX_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
STREAM_CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class FrozenKrakenRequest:
    source_kind: str
    method: str
    host: str
    target: str
    url: str
    max_response_bytes: int = MAX_ARCHIVE_BYTES

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/zip, application/octet-stream, */*",
            "User-Agent": "rnnyrgs-pit-research-acquisition/1",
            "Connection": "close",
        }


@dataclass(frozen=True)
class StreamFetchResult:
    status: int
    headers: dict[str, str]
    response_sha256: str
    byte_count: int
    started_at: str
    completed_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"duplicate JSON object key: {key}")
        parsed[key] = value
    return parsed


def _reject_nonstandard_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _strict_json(raw: bytes, *, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} rejected: {exc}") from exc


def _canonical_artifact_digest(contract: dict[str, Any]) -> str:
    unsigned = dict(contract)
    unsigned.pop("artifact_sha256", None)
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _contract_bytes(repo_root: str | Path | None = None) -> bytes:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    return (root / CONTRACT_PATH).resolve().read_bytes()


def load_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Load exactly the frozen #779 scientific contract and fail closed on drift."""
    raw = _contract_bytes(repo_root)
    payload = _strict_json(raw, label="ETH session replication contract")
    if not isinstance(payload, dict):
        raise ValueError("ETH session replication contract root must be an object")
    if payload.get("replication_id") != CONTRACT_ID:
        raise ValueError("ETH session replication contract identity mismatch")
    if payload.get("artifact_sha256") != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("ETH session replication artifact identity mismatch")
    if _canonical_artifact_digest(payload) != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("ETH session replication artifact self-digest mismatch")

    data = payload.get("data_contract")
    if not isinstance(data, dict):
        raise ValueError("ETH session data contract missing")
    if data.get("required_incremental_archives") != list(SOURCE_URLS.values()):
        raise ValueError("Kraken incremental archive URLs drifted from frozen contract")
    if data.get("instrument") != "ETH/USD spot pair as named by the frozen Kraken archive manifest":
        raise ValueError("frozen Kraken instrument contract changed")
    if data.get("bar_interval") != "60m" or data.get("timezone") != "UTC":
        raise ValueError("frozen Kraken cadence/timezone contract changed")
    if data.get("protected_shadow_start_utc") != "2026-07-01T00:00:00Z":
        raise ValueError("protected shadow boundary changed")
    if data.get("screen_may_read_protected_shadow") is not False:
        raise ValueError("protected shadow must remain sealed")
    if data.get("no_paid_data_required") is not True:
        raise ValueError("Kraken archive path must remain zero-new-cost")

    authority = payload.get("screening_authority")
    execution = payload.get("execution_rules")
    if not isinstance(authority, dict) or not isinstance(execution, dict):
        raise ValueError("screening/execution authority blocks missing")
    if authority.get("screen_started") is not False:
        raise ValueError("trusted acquisition cannot consume an already-started screen")
    if authority.get("protected_shadow_opened") is not False:
        raise ValueError("protected shadow must remain unopened")
    if authority.get("trade_authority") is not False or authority.get("promotion_authority") is not False:
        raise ValueError("trusted acquisition cannot carry trade/promotion authority")
    if execution.get("broker_connected") is not False or execution.get("live_trading") is not False:
        raise ValueError("broker/live trading must remain OFF")
    return payload


def contract_bytes_sha256(repo_root: str | Path | None = None) -> str:
    return hashlib.sha256(_contract_bytes(repo_root)).hexdigest()


def freeze_kraken_request(*, source_kind: str) -> FrozenKrakenRequest:
    url = SOURCE_URLS.get(source_kind)
    if url is None:
        raise ValueError("unsupported Kraken ETH-session archive source kind")
    prefix = f"https://{HOST}"
    if not url.startswith(prefix + "/"):
        raise ValueError("frozen Kraken URL host mismatch")
    target = url[len(prefix) :]
    if any(token in target for token in ("..", "\\", "\x00", "?", "#", "%")):
        raise ValueError("frozen Kraken archive target is unsafe")
    return FrozenKrakenRequest(
        source_kind=source_kind,
        method="GET",
        host=HOST,
        target=target,
        url=url,
    )


def _lower_headers(items: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in items:
        lower = key.strip().lower()
        clean = value.strip()
        if lower in result:
            result[lower] = result[lower] + ", " + clean
        else:
            result[lower] = clean
    return result


def _parse_content_length(headers: dict[str, str], *, maximum: int) -> int | None:
    value = headers.get("content-length")
    if value in (None, ""):
        return None
    if not value.isdigit():
        raise ValueError("Kraken Content-Length must be a nonnegative integer when present")
    size = int(value)
    if size <= 0:
        raise ValueError("Kraken archive Content-Length must be positive")
    if size > maximum:
        raise ValueError("Kraken archive exceeds frozen byte limit")
    return size


def fetch_to_file(
    request: FrozenKrakenRequest,
    *,
    destination: str | Path,
    timeout_seconds: float = 60.0,
) -> StreamFetchResult:
    """Stream one exact provider object to disk over direct TLS; never follow redirects."""
    if request.method != "GET":
        raise ValueError("only GET is supported")
    destination_path = Path(destination).resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    partial = destination_path.with_name(destination_path.name + ".partial")
    partial.unlink(missing_ok=True)

    started_at = _utc_now()
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(
        request.host,
        443,
        timeout=timeout_seconds,
        context=context,
    )
    digest = hashlib.sha256()
    total = 0
    try:
        connection.request(request.method, request.target, headers=request.headers())
        response = connection.getresponse()
        status = int(response.status)
        headers = _lower_headers(response.getheaders())
        if status != 200:
            response.read(65536)
            raise ValueError(f"Kraken returned non-authoritative HTTP status {status}")
        declared_size = _parse_content_length(headers, maximum=request.max_response_bytes)
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > request.max_response_bytes:
                    raise ValueError("Kraken archive exceeds frozen byte limit")
                digest.update(chunk)
                handle.write(chunk)
        if total <= 0:
            raise ValueError("Kraken archive response is empty")
        if declared_size is not None and total != declared_size:
            raise ValueError("Kraken archive byte count does not match Content-Length")
        partial.replace(destination_path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    finally:
        connection.close()

    return StreamFetchResult(
        status=200,
        headers=headers,
        response_sha256=digest.hexdigest(),
        byte_count=total,
        started_at=started_at,
        completed_at=_utc_now(),
    )


def validate_archive(path: str | Path) -> dict[str, Any]:
    """Validate only transport/container facts needed before deterministic data preflight."""
    archive_path = Path(path).resolve()
    if not zipfile.is_zipfile(archive_path):
        raise ValueError("Kraken response is not a valid ZIP archive")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            names = archive.namelist()
            if names.count("MANIFEST.json") != 1:
                raise ValueError("Kraken archive must contain exactly one root MANIFEST.json")
            info = archive.getinfo("MANIFEST.json")
            if info.flag_bits & 0x1:
                raise ValueError("Kraken MANIFEST.json must not be encrypted")
            if info.file_size <= 0 or info.file_size > MAX_MANIFEST_BYTES:
                raise ValueError("Kraken MANIFEST.json size is outside frozen bound")
            manifest = archive.read(info)
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("Kraken ZIP container could not be safely inspected") from exc

    manifest_json = _strict_json(manifest, label="Kraken MANIFEST.json")
    if not isinstance(manifest_json, (dict, list)):
        raise ValueError("Kraken MANIFEST.json root must be an object or array")
    return {
        "manifest_bytes": manifest,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "manifest_byte_count": len(manifest),
        "zip_member_count": len(names),
    }


def canonical_receipt(
    request: FrozenKrakenRequest,
    result: StreamFetchResult,
    *,
    github_context: dict[str, Any],
    source_contract_bytes_sha256: str,
    archive_metadata: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "kraken_eth_session_archive_acquisition_receipt.v1",
        "source_contract_id": CONTRACT_ID,
        "source_contract_artifact_sha256": CONTRACT_ARTIFACT_SHA256,
        "source_contract_bytes_sha256": source_contract_bytes_sha256,
        "consumer": "EXT-ETH-SESSION-REVERSAL-001-v1 data provenance preflight",
        "source_kind": request.source_kind,
        "request": {
            "method": request.method,
            "url": request.url,
            "range_header": None,
        },
        "response": {
            "status": result.status,
            "sha256": result.response_sha256,
            "byte_count": result.byte_count,
            "content_type": result.headers.get("content-type"),
            "etag": result.headers.get("etag"),
            "last_modified": result.headers.get("last-modified"),
        },
        "provider_metadata": {
            "manifest_sha256": archive_metadata["manifest_sha256"],
            "manifest_byte_count": archive_metadata["manifest_byte_count"],
            "zip_member_count": archive_metadata["zip_member_count"],
        },
        "acquisition": {
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            **github_context,
        },
        "authority": "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION",
        "scientific_authority": {
            "archive_provenance_possible_after_attestation": True,
            "manifest_provenance_possible_after_attestation": True,
            "pair_resolution_authority": False,
            "timestamp_semantics_authority": False,
            "normalized_rows_authority": False,
            "strategy_screen_authority": False,
            "protected_shadow_authority": False,
            "profitability_claim_authority": False,
            "promotion_authority": False,
            "broker_connected": False,
            "live_trading": False,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(STREAM_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def write_bundle(
    response_path: str | Path,
    manifest_bytes: bytes,
    receipt: dict[str, Any],
    *,
    output_dir: str | Path,
) -> dict[str, str]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    response = Path(response_path).resolve()
    receipt_path = out / "receipt.json"
    manifest_path = out / "MANIFEST.json"
    bundle_path = out / "trusted-acquisition.tar"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_bytes(manifest_bytes)

    with tarfile.open(bundle_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path, arcname in (
            (receipt_path, "receipt.json"),
            (manifest_path, "MANIFEST.json"),
            (response, "response.bin"),
        ):
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return {
        "bundle_path": str(bundle_path),
        "bundle_sha256": _file_sha256(bundle_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-kind", required=True, choices=tuple(SOURCE_URLS))
    parser.add_argument("--output-dir", default="trusted-acquisition-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_contract()
    contract_sha = contract_bytes_sha256()
    request = freeze_kraken_request(source_kind=args.source_kind)
    context = trusted_github_context()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    response_path = out / "response.bin"
    result = fetch_to_file(request, destination=response_path)
    metadata = validate_archive(response_path)
    if _file_sha256(response_path) != result.response_sha256:
        raise ValueError("retained Kraken archive bytes drifted after acquisition")
    receipt = canonical_receipt(
        request,
        result,
        github_context=context,
        source_contract_bytes_sha256=contract_sha,
        archive_metadata=metadata,
    )
    written = write_bundle(
        response_path,
        metadata["manifest_bytes"],
        receipt,
        output_dir=out,
    )
    print(
        json.dumps(
            {
                "status": "TRUSTED_FETCH_COMPLETE_PENDING_ATTESTATION_AND_DATA_PREFLIGHT",
                "source_contract_id": CONTRACT_ID,
                "source_contract_artifact_sha256": CONTRACT_ARTIFACT_SHA256,
                "source_contract_bytes_sha256": contract_sha,
                "source_kind": request.source_kind,
                "request_url": request.url,
                "receipt_sha256": receipt["receipt_sha256"],
                "response_sha256": receipt["response"]["sha256"],
                "manifest_sha256": receipt["provider_metadata"]["manifest_sha256"],
                "bundle_sha256": written["bundle_sha256"],
                "strategy_screen_authority": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Trusted direct Binance object acquisition for frozen C101-H development data.

This module extends the canonical trusted acquisition workflow only for the exact
development-period Binance public-data objects required by #529 C101-H. It refuses
protected months (2026-09 onward), arbitrary URLs/paths, unsupported symbols and
timeframes. It grants provenance only; no strategy, promotion, broker or trading authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.parse import quote

from trusted_remote_acquisition import (
    FetchResult,
    FrozenRequest,
    fetch_once,
    trusted_github_context,
)

CONTRACT_PATH = "orchestration/data/c101h_binance_direct_acquisition_contract_v1.json"
CONTRACT_SHA256 = "4f1f969ba5ca7b859e0b5c18cd88b3ca76bd99c35ac9360f1c99828226860b1f"
CONTRACT_ID = "C101H-BINANCE-DIRECT-ACQUISITION-001-v1"
HOST = "data.binance.vision"
ALLOWED_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})
DEVELOPMENT_CUTOFF_MONTH = "2026-08"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MONTH_RE = re.compile(r"^20\d{2}-(?:0[1-9]|1[0-2])$")
ARCHIVE_PATTERNS = (
    re.compile(
        r"^data/spot/monthly/klines/(?P<symbol>[A-Z0-9]+)/1h/"
        r"(?P=symbol)-1h-(?P<month>20\d{2}-(?:0[1-9]|1[0-2]))\.zip$"
    ),
    re.compile(
        r"^data/futures/um/monthly/klines/(?P<symbol>[A-Z0-9]+)/1h/"
        r"(?P=symbol)-1h-(?P<month>20\d{2}-(?:0[1-9]|1[0-2]))\.zip$"
    ),
    re.compile(
        r"^data/futures/um/monthly/fundingRate/(?P<symbol>[A-Z0-9]+)/"
        r"(?P=symbol)-fundingRate-(?P<month>20\d{2}-(?:0[1-9]|1[0-2]))\.zip$"
    ),
)
CHECKSUM_RE = re.compile(
    r"^(?P<sha>[0-9a-fA-F]{64})[ \t]+\*?(?P<filename>[^/\\\r\n]+\.zip)\r?\n?$"
)


def load_contract(repo_root: str | Path | None = None) -> dict:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("C101-H Binance acquisition contract digest mismatch")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("artifact_id") != CONTRACT_ID:
        raise ValueError("C101-H Binance acquisition contract identity mismatch")
    return payload


def _archive_metadata(object_path: str) -> tuple[str, str]:
    if not isinstance(object_path, str) or not object_path:
        raise ValueError("object_path must be non-empty")
    if object_path.startswith("/") or "\\" in object_path or "\x00" in object_path:
        raise ValueError("Binance object path is unsafe")
    path = PurePosixPath(object_path)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("Binance object path contains forbidden traversal")
    if "%" in object_path or "?" in object_path or "#" in object_path:
        raise ValueError("Binance object path must be an exact unescaped provider path")
    for pattern in ARCHIVE_PATTERNS:
        match = pattern.fullmatch(object_path)
        if not match:
            continue
        symbol = match.group("symbol")
        month = match.group("month")
        if symbol not in ALLOWED_SYMBOLS:
            raise ValueError("Binance object symbol is not frozen for C101-H")
        if not MONTH_RE.fullmatch(month):
            raise ValueError("Binance object month is malformed")
        if month > DEVELOPMENT_CUTOFF_MONTH:
            raise ValueError("protected C101-H month acquisition is forbidden")
        return symbol, month
    raise ValueError("Binance object path is outside frozen C101-H archive families")


def freeze_binance_c101h_request(*, source_kind: str, object_path: str) -> FrozenRequest:
    if source_kind not in {"BINANCE_C101H_ARCHIVE", "BINANCE_C101H_CHECKSUM"}:
        raise ValueError("unsupported C101-H Binance source kind")
    archive_path = object_path
    if source_kind == "BINANCE_C101H_CHECKSUM":
        if not object_path.endswith(".CHECKSUM"):
            raise ValueError("checksum object must be exact archive path plus .CHECKSUM")
        archive_path = object_path[: -len(".CHECKSUM")]
    _archive_metadata(archive_path)
    target = "/" + quote(object_path, safe="/._-")
    return FrozenRequest(
        source_kind=source_kind,
        method="GET",
        host=HOST,
        target=target,
        url=f"https://{HOST}{target}",
        max_response_bytes=(
            MAX_ARCHIVE_BYTES
            if source_kind == "BINANCE_C101H_ARCHIVE"
            else MAX_CHECKSUM_BYTES
        ),
    )


def _validate_provider_body(
    request: FrozenRequest, body: bytes
) -> dict[str, str | None]:
    if request.source_kind == "BINANCE_C101H_ARCHIVE":
        if len(body) < 4 or not body.startswith(b"PK\x03\x04"):
            raise ValueError("Binance archive response is not a ZIP local-file stream")
        return {
            "declared_archive_sha256": None,
            "archive_filename": request.target.rsplit("/", 1)[-1],
        }

    if request.source_kind != "BINANCE_C101H_CHECKSUM":
        raise ValueError("unexpected C101-H source kind")
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("Binance checksum response must be ASCII") from exc
    match = CHECKSUM_RE.fullmatch(text)
    if not match:
        raise ValueError("Binance checksum response has unexpected format")
    expected_archive = request.target.rsplit("/", 1)[-1].removesuffix(".CHECKSUM")
    if match.group("filename") != expected_archive:
        raise ValueError("Binance checksum filename does not match frozen archive object")
    return {
        "declared_archive_sha256": match.group("sha").lower(),
        "archive_filename": expected_archive,
    }


def canonical_receipt(
    request: FrozenRequest,
    result: FetchResult,
    *,
    github_context: dict,
    provider_metadata: dict[str, str | None],
) -> dict:
    payload = {
        "schema": "c101h_binance_direct_acquisition_receipt.v1",
        "source_contract_id": CONTRACT_ID,
        "consumer": "#529 C101-H delta-neutral funding carry",
        "source_kind": request.source_kind,
        "request": {
            "method": request.method,
            "url": request.url,
            "range_header": None,
        },
        "response": {
            "status": result.status,
            "sha256": hashlib.sha256(result.body).hexdigest(),
            "byte_count": len(result.body),
            "content_type": result.headers.get("content-type"),
            "etag": result.headers.get("etag"),
            "last_modified": result.headers.get("last-modified"),
        },
        "provider_metadata": provider_metadata,
        "acquisition": {
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            **github_context,
        },
        "authority": (
            "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION"
        ),
        "protected_evidence": "DEVELOPMENT_MONTHS_ONLY_THROUGH_2026_08",
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_bundle(
    request: FrozenRequest,
    result: FetchResult,
    *,
    output_dir: str | Path,
    github_context: dict,
) -> dict:
    provider_metadata = _validate_provider_body(request, result.body)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    response_path = out / "response.bin"
    receipt_path = out / "receipt.json"
    bundle_path = out / "trusted-acquisition.tar"
    response_path.write_bytes(result.body)
    receipt = canonical_receipt(
        request,
        result,
        github_context=github_context,
        provider_metadata=provider_metadata,
    )
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with tarfile.open(bundle_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path, arcname in (
            (receipt_path, "receipt.json"),
            (response_path, "response.bin"),
        ):
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return {
        "receipt": receipt,
        "bundle_path": str(bundle_path),
        "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("BINANCE_C101H_ARCHIVE", "BINANCE_C101H_CHECKSUM"),
    )
    parser.add_argument("--object-path", required=True)
    parser.add_argument("--output-dir", default="trusted-acquisition-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_contract()
    request = freeze_binance_c101h_request(
        source_kind=args.source_kind, object_path=args.object_path
    )
    context = trusted_github_context()
    result = fetch_once(request)
    written = write_bundle(
        request, result, output_dir=args.output_dir, github_context=context
    )
    print(
        json.dumps(
            {
                "status": "TRUSTED_FETCH_COMPLETE_PENDING_ATTESTATION",
                "source_kind": request.source_kind,
                "request_url": request.url,
                "receipt_sha256": written["receipt"]["receipt_sha256"],
                "response_sha256": written["receipt"]["response"]["sha256"],
                "bundle_sha256": written["bundle_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

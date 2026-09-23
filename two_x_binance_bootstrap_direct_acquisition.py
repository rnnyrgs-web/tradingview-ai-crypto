"""Trusted direct Binance acquisition for one frozen 2x Cohort-001 bootstrap canary.

This helper deliberately authorizes only the exact BTCUSDT Spot 1d January-2021
archive/checksum pair frozen by ``2X-BINANCE-COHORT-BOOTSTRAP-SLICE-001-v1``.
It reuses the canonical trusted GitHub acquisition boundary without borrowing the
scientific authority of the separate C101-H development-data contract.

Provider bytes acquired here grant provenance only after external GitHub artifact
attestation verification. They do not grant Cohort membership, USD-liquidity,
historical-label, matched-control, candidate, prediction, promotion, broker, or live
trading authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import quote

from trusted_remote_acquisition import (
    FetchResult,
    FrozenRequest,
    fetch_once,
    trusted_github_context,
)

CONTRACT_PATH = "money_intelligence/2x_binance_cohort_bootstrap_slice_v1.json"
CONTRACT_ID = "2X-BINANCE-COHORT-BOOTSTRAP-SLICE-001-v1"
HOST = "data.binance.vision"
ARCHIVE_SOURCE_KIND = "BINANCE_2X_COHORT_BOOTSTRAP_ARCHIVE"
CHECKSUM_SOURCE_KIND = "BINANCE_2X_COHORT_BOOTSTRAP_CHECKSUM"
ARCHIVE_OBJECT_PATH = (
    "data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2021-01.zip"
)
CHECKSUM_OBJECT_PATH = ARCHIVE_OBJECT_PATH + ".CHECKSUM"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
CHECKSUM_RE = re.compile(
    r"^(?P<sha>[0-9a-fA-F]{64})[ \t]+\*?(?P<filename>[^/\\\r\n]+\.zip)\r?\n?$"
)


def _contract_bytes(repo_root: str | Path | None = None) -> bytes:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    return (root / CONTRACT_PATH).resolve().read_bytes()


def load_contract(repo_root: str | Path | None = None) -> dict:
    """Load and fail-close the exact frozen bootstrap contract shape we consume."""
    raw = _contract_bytes(repo_root)
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("artifact_id") != CONTRACT_ID:
        raise ValueError("2x Binance bootstrap contract identity mismatch")

    requirements = payload.get("trusted_acquisition_requirements")
    if not isinstance(requirements, dict):
        raise ValueError("2x Binance bootstrap trusted acquisition requirements missing")
    expected_source_kinds = [ARCHIVE_SOURCE_KIND, CHECKSUM_SOURCE_KIND]
    if requirements.get("required_new_source_kinds") != expected_source_kinds:
        raise ValueError("2x Binance bootstrap source-kind contract mismatch")
    if requirements.get("c101h_source_kind_reuse_forbidden") is not True:
        raise ValueError("C101-H source-kind reuse must remain forbidden")

    objects = payload.get("provider_objects")
    if not isinstance(objects, dict):
        raise ValueError("2x Binance bootstrap provider objects missing")
    archive = objects.get("archive")
    checksum = objects.get("checksum")
    if not isinstance(archive, dict) or not isinstance(checksum, dict):
        raise ValueError("2x Binance bootstrap provider object contract malformed")
    if archive.get("source_kind") != ARCHIVE_SOURCE_KIND or archive.get("object_path") != ARCHIVE_OBJECT_PATH:
        raise ValueError("2x Binance bootstrap archive contract mismatch")
    if checksum.get("source_kind") != CHECKSUM_SOURCE_KIND or checksum.get("object_path") != CHECKSUM_OBJECT_PATH:
        raise ValueError("2x Binance bootstrap checksum contract mismatch")
    if archive.get("url") != f"https://{HOST}/{ARCHIVE_OBJECT_PATH}":
        raise ValueError("2x Binance bootstrap archive URL mismatch")
    if checksum.get("url") != f"https://{HOST}/{CHECKSUM_OBJECT_PATH}":
        raise ValueError("2x Binance bootstrap checksum URL mismatch")

    allowed = payload.get("allowed_scientific_consumers")
    if not isinstance(allowed, dict) or set(allowed) != {"decision_price"}:
        raise ValueError("bootstrap acquisition must remain price-only")
    blocked = payload.get("blocked_scientific_consumers")
    if not isinstance(blocked, dict) or "trailing_30d_median_quote_volume_usd" not in blocked:
        raise ValueError("USD liquidity must remain blocked in bootstrap contract")
    if payload.get("broker_live_trading") != "OFF":
        raise ValueError("broker/live trading must remain OFF")
    return payload


def contract_sha256(repo_root: str | Path | None = None) -> str:
    return hashlib.sha256(_contract_bytes(repo_root)).hexdigest()


def freeze_binance_2x_bootstrap_request(*, source_kind: str, object_path: str) -> FrozenRequest:
    """Freeze exactly one archive or its checksum; reject every broader request."""
    expected_path = {
        ARCHIVE_SOURCE_KIND: ARCHIVE_OBJECT_PATH,
        CHECKSUM_SOURCE_KIND: CHECKSUM_OBJECT_PATH,
    }.get(source_kind)
    if expected_path is None:
        raise ValueError("unsupported 2x Binance bootstrap source kind")
    if object_path != expected_path:
        raise ValueError("object_path is outside the exact frozen 2x bootstrap slice")
    if any(token in object_path for token in ("..", "\\", "\x00", "?", "#", "%")):
        raise ValueError("Binance object path is unsafe")

    target = "/" + quote(object_path, safe="/._-")
    return FrozenRequest(
        source_kind=source_kind,
        method="GET",
        host=HOST,
        target=target,
        url=f"https://{HOST}{target}",
        max_response_bytes=(MAX_ARCHIVE_BYTES if source_kind == ARCHIVE_SOURCE_KIND else MAX_CHECKSUM_BYTES),
    )


def _validate_provider_body(request: FrozenRequest, body: bytes) -> dict[str, str | None]:
    if request.source_kind == ARCHIVE_SOURCE_KIND:
        if len(body) < 4 or not body.startswith(b"PK\x03\x04"):
            raise ValueError("Binance bootstrap archive response is not a ZIP local-file stream")
        return {
            "declared_archive_sha256": None,
            "archive_filename": ARCHIVE_OBJECT_PATH.rsplit("/", 1)[-1],
        }

    if request.source_kind != CHECKSUM_SOURCE_KIND:
        raise ValueError("unexpected 2x Binance bootstrap source kind")
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("Binance bootstrap checksum response must be ASCII") from exc
    match = CHECKSUM_RE.fullmatch(text)
    if not match:
        raise ValueError("Binance bootstrap checksum response has unexpected format")
    expected_archive = ARCHIVE_OBJECT_PATH.rsplit("/", 1)[-1]
    if match.group("filename") != expected_archive:
        raise ValueError("Binance bootstrap checksum filename does not match frozen archive object")
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
    source_contract_sha256: str,
) -> dict:
    payload = {
        "schema": "two_x_binance_bootstrap_direct_acquisition_receipt.v1",
        "source_contract_id": CONTRACT_ID,
        "source_contract_sha256": source_contract_sha256,
        "consumer": "#705/#710 BTCUSDT Spot 1d Cohort-001 provenance canary",
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
        "authority": "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION",
        "scientific_authority": {
            "provenance_bound_price_consumer_possible_after_downstream_validation": True,
            "usd_liquidity_authority": False,
            "cohort_membership_authority": False,
            "historical_label_authority": False,
            "matched_control_authority": False,
            "prospective_candidate_authority": False,
            "prediction_authority": False,
            "promotion_authority": False,
            "broker_connected": False,
            "live_trading": False,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_bundle(
    request: FrozenRequest,
    result: FetchResult,
    *,
    output_dir: str | Path,
    github_context: dict,
    source_contract_sha256: str,
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
        source_contract_sha256=source_contract_sha256,
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with tarfile.open(bundle_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path, arcname in ((receipt_path, "receipt.json"), (response_path, "response.bin")):
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
    parser.add_argument("--source-kind", required=True, choices=(ARCHIVE_SOURCE_KIND, CHECKSUM_SOURCE_KIND))
    parser.add_argument("--object-path", required=True)
    parser.add_argument("--output-dir", default="trusted-acquisition-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_contract()
    source_contract_sha256 = contract_sha256()
    request = freeze_binance_2x_bootstrap_request(source_kind=args.source_kind, object_path=args.object_path)
    context = trusted_github_context()
    result = fetch_once(request)
    written = write_bundle(
        request,
        result,
        output_dir=args.output_dir,
        github_context=context,
        source_contract_sha256=source_contract_sha256,
    )
    print(
        json.dumps(
            {
                "status": "TRUSTED_FETCH_COMPLETE_PENDING_ATTESTATION",
                "source_contract_id": CONTRACT_ID,
                "source_contract_sha256": source_contract_sha256,
                "source_kind": request.source_kind,
                "request_url": request.url,
                "receipt_sha256": written["receipt"]["receipt_sha256"],
                "response_sha256": written["receipt"]["response"]["sha256"],
                "bundle_sha256": written["bundle_sha256"],
                "usd_liquidity_authority": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

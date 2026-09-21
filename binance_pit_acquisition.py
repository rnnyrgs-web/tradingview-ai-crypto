"""Trusted-fetch planning for the frozen C101-H Binance PIT data contract.

This module does not perform network I/O and grants no data-ready authority.  It
resolves only the predeclared Binance Vision objects that the dedicated GitHub
Actions acquisition workflow may fetch.  The workflow, not a caller-authored
local file, is the trust boundary: fetched bytes and their receipt are later
covered by a GitHub artifact attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from binance_pit_archive import verify_archive_pair

ARCHIVE_HOST = "https://data.binance.vision"
ALLOWED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEVELOPMENT_START_MONTH = "2023-07"
DEVELOPMENT_END_MONTH = "2026-08"
MONTH_RE = re.compile(r"^(20\d{2})-(0[1-9]|1[0-2])$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SOURCE_PATHS = {
    "spot_kline": "data/spot/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip",
    "usdm_perp_kline": "data/futures/um/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip",
    "usdm_funding_rate": "data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip",
}

TRUST_POLICY = {
    "attestation_predicate_type": "https://slsa.dev/provenance/v1",
    "signer_workflow": "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/c101h_binance_pit_acquisition.yml",
    "source_ref": "refs/heads/main",
    "repository": "rnnyrgs-web/tradingview-ai-crypto",
}


@dataclass(frozen=True)
class FrozenSourceRequest:
    source_kind: str
    symbol: str
    month: str
    archive_filename: str
    archive_url: str
    checksum_url: str


def _month_index(value: str) -> int:
    match = MONTH_RE.fullmatch(value)
    if not match:
        raise ValueError("month must be YYYY-MM")
    return int(match.group(1)) * 12 + int(match.group(2))


def resolve_frozen_source(source_kind: str, symbol: str, month: str) -> FrozenSourceRequest:
    """Resolve exactly one predeclared Binance object; fail closed outside the frozen set."""
    if source_kind not in SOURCE_PATHS:
        raise ValueError(f"unsupported source_kind: {source_kind}")
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"symbol is outside frozen C101-H universe: {symbol}")
    month_value = _month_index(month)
    if not _month_index(DEVELOPMENT_START_MONTH) <= month_value <= _month_index(DEVELOPMENT_END_MONTH):
        raise ValueError("month is outside frozen C101-H development coverage")

    relative_path = SOURCE_PATHS[source_kind].format(symbol=symbol, month=month)
    archive_filename = relative_path.rsplit("/", 1)[-1]
    archive_url = f"{ARCHIVE_HOST}/{relative_path}"
    return FrozenSourceRequest(
        source_kind=source_kind,
        symbol=symbol,
        month=month,
        archive_filename=archive_filename,
        archive_url=archive_url,
        checksum_url=f"{archive_url}.CHECKSUM",
    )


def _require_https_url(value: str, field: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{field} contains forbidden URL components")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_acquisition_receipt(
    request: FrozenSourceRequest,
    *,
    archive_path: Path,
    checksum_path: Path,
    archive_http_status: int,
    archive_final_url: str,
    checksum_http_status: int,
    checksum_final_url: str,
    captured_at_utc: str,
    workflow_repository: str,
    workflow_ref: str,
    workflow_sha: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
) -> dict[str, Any]:
    """Build a receipt payload for bytes fetched inside the trusted acquisition workflow.

    The receipt itself is not trusted merely because this function emitted it.  It
    becomes admissible provenance only after GitHub attests the receipt and raw
    byte subjects and a consumer verifies that attestation against TRUST_POLICY.
    """
    if archive_path.name != request.archive_filename:
        raise ValueError("archive filename does not match frozen source request")
    if checksum_path.name != f"{request.archive_filename}.CHECKSUM":
        raise ValueError("checksum filename does not match frozen source request")
    if archive_http_status != 200 or checksum_http_status != 200:
        raise ValueError("both Binance source requests must complete with HTTP 200")
    _require_https_url(archive_final_url, "archive_final_url")
    _require_https_url(checksum_final_url, "checksum_final_url")

    captured = datetime.fromisoformat(captured_at_utc.replace("Z", "+00:00"))
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("captured_at_utc must include timezone")
    if captured.astimezone(timezone.utc).isoformat() != captured.isoformat():
        captured = captured.astimezone(timezone.utc)

    if workflow_repository != TRUST_POLICY["repository"]:
        raise ValueError("workflow repository is outside trusted acquisition policy")
    if workflow_ref != TRUST_POLICY["source_ref"]:
        raise ValueError("trusted acquisition must run from refs/heads/main")
    if not re.fullmatch(r"[0-9a-f]{40}", workflow_sha):
        raise ValueError("workflow_sha must be a full lowercase git SHA")
    if not workflow_run_id.isdigit() or not workflow_run_attempt.isdigit():
        raise ValueError("workflow run metadata must be numeric")

    verified = verify_archive_pair(archive_path, checksum_path)
    archive_sha = _sha256_file(archive_path)
    sidecar_sha = _sha256_file(checksum_path)
    if archive_sha != verified.archive_sha256 or sidecar_sha != verified.checksum_sidecar_sha256:
        raise RuntimeError("local archive verification digest disagreement")
    if not SHA256_RE.fullmatch(archive_sha) or not SHA256_RE.fullmatch(sidecar_sha):
        raise RuntimeError("unexpected SHA-256 encoding")

    return {
        "schema_version": 1,
        "consumer": "C101-H",
        "status": "FETCHED_AWAITING_ATTESTATION_VERIFICATION",
        "data_ready_authority": False,
        "source_request": asdict(request),
        "http": {
            "archive": {
                "requested_url": request.archive_url,
                "final_url": archive_final_url,
                "status": archive_http_status,
            },
            "checksum": {
                "requested_url": request.checksum_url,
                "final_url": checksum_final_url,
                "status": checksum_http_status,
            },
        },
        "captured_at_utc": captured.astimezone(timezone.utc).isoformat(),
        "archive_sha256": archive_sha,
        "checksum_sidecar_sha256": sidecar_sha,
        "csv_member": verified.csv_member,
        "workflow": {
            "repository": workflow_repository,
            "ref": workflow_ref,
            "sha": workflow_sha,
            "run_id": workflow_run_id,
            "run_attempt": workflow_run_attempt,
            "signer_workflow": TRUST_POLICY["signer_workflow"],
        },
        "required_consumer_verification": {
            "tool": "gh attestation verify",
            "repo": TRUST_POLICY["repository"],
            "signer_workflow": TRUST_POLICY["signer_workflow"],
            "source_ref": TRUST_POLICY["source_ref"],
            "predicate_type": TRUST_POLICY["attestation_predicate_type"],
            "subjects_must_include": [
                "request.json",
                "receipt.json",
                request.archive_filename,
                f"{request.archive_filename}.CHECKSUM",
            ],
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cmd_resolve(args: argparse.Namespace) -> None:
    request = resolve_frozen_source(args.source_kind, args.symbol, args.month)
    _write_json(Path(args.output), asdict(request))


def _cmd_receipt(args: argparse.Namespace) -> None:
    raw = json.loads(Path(args.request).read_text(encoding="utf-8"))
    request = FrozenSourceRequest(**raw)
    canonical = resolve_frozen_source(request.source_kind, request.symbol, request.month)
    if request != canonical:
        raise ValueError("request file does not match canonical frozen source resolution")
    payload = build_acquisition_receipt(
        request,
        archive_path=Path(args.archive),
        checksum_path=Path(args.checksum),
        archive_http_status=int(args.archive_http_status),
        archive_final_url=args.archive_final_url,
        checksum_http_status=int(args.checksum_http_status),
        checksum_final_url=args.checksum_final_url,
        captured_at_utc=args.captured_at_utc,
        workflow_repository=args.workflow_repository,
        workflow_ref=args.workflow_ref,
        workflow_sha=args.workflow_sha,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
    )
    _write_json(Path(args.output), payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--source-kind", required=True, choices=sorted(SOURCE_PATHS))
    resolve.add_argument("--symbol", required=True, choices=ALLOWED_SYMBOLS)
    resolve.add_argument("--month", required=True)
    resolve.add_argument("--output", required=True)
    resolve.set_defaults(func=_cmd_resolve)

    receipt = sub.add_parser("receipt")
    receipt.add_argument("--request", required=True)
    receipt.add_argument("--archive", required=True)
    receipt.add_argument("--checksum", required=True)
    receipt.add_argument("--archive-http-status", required=True)
    receipt.add_argument("--archive-final-url", required=True)
    receipt.add_argument("--checksum-http-status", required=True)
    receipt.add_argument("--checksum-final-url", required=True)
    receipt.add_argument("--captured-at-utc", required=True)
    receipt.add_argument("--workflow-repository", required=True)
    receipt.add_argument("--workflow-ref", required=True)
    receipt.add_argument("--workflow-sha", required=True)
    receipt.add_argument("--workflow-run-id", required=True)
    receipt.add_argument("--workflow-run-attempt", required=True)
    receipt.add_argument("--output", required=True)
    receipt.set_defaults(func=_cmd_receipt)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

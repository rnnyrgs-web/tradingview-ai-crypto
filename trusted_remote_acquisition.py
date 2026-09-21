"""Trusted remote-acquisition boundary for PIT research evidence.

This module does one narrow job: from a trusted GitHub Actions execution on canonical
``main``, fetch bytes from one of a small allowlisted provider request shapes and emit
a canonical receipt binding the exact request, response bytes and workflow identity.

A local file/hash/official-looking URL is *not* trusted provider evidence. Downstream
research may treat a retained response as provider-authenticated only after the
``trusted-acquisition.tar`` subject has a valid GitHub artifact attestation for this
repository and the receipt validates against the retained ``response.bin``.

This module grants no label, candidate, strategy, promotion, broker or trading authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import tarfile
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

CONTRACT_PATH = "money_intelligence/trusted_remote_acquisition_contract_v1.json"
CONTRACT_SHA256 = "cc8a90a1659720001d97844d7489587a8f92d1fa8f9293bbacc7d34a79a946a5"
CONTRACT_ID = "PIT-TRUSTED-REMOTE-ACQUISITION-001-v1"
EXPECTED_REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
EXPECTED_EVENT = "workflow_dispatch"
EXPECTED_REF = "refs/heads/main"
EXPECTED_WORKFLOW_PATH = ".github/workflows/pit-trusted-remote-acquisition.yml"
EXPECTED_WORKFLOW_REF = f"{EXPECTED_REPOSITORY}/{EXPECTED_WORKFLOW_PATH}@{EXPECTED_REF}"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COLLECTION_RE = re.compile(r"^CC-MAIN-\d{4}-\d{2}$")
WARC_FILENAME_RE = re.compile(
    r"^crawl-data/(CC-MAIN-\d{4}-\d{2})/.+/warc/[^/]+\.warc\.gz$"
)
MAX_BINANCE_BYTES = 8 * 1024 * 1024
MAX_CC_INDEX_BYTES = 8 * 1024 * 1024
MAX_CC_WARC_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class FrozenRequest:
    source_kind: str
    method: str
    host: str
    target: str
    url: str
    range_header: str | None = None
    predecessor_receipt_sha256: str | None = None
    max_response_bytes: int = MAX_BINANCE_BYTES

    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "User-Agent": "rnnyrgs-pit-research-acquisition/1",
            "Connection": "close",
        }
        if self.range_header is not None:
            headers["Range"] = self.range_header
        return headers


@dataclass(frozen=True)
class FetchResult:
    status: int
    headers: dict[str, str]
    body: bytes
    started_at: str
    completed_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_sha256(value: str | None, *, field: str, optional: bool = False) -> str | None:
    if value in (None, "") and optional:
        return None
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return value


def _clean_https_url(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be non-empty")
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError(f"{field} must be clean HTTPS without credentials or fragment")
    if parts.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(f"{field} loopback targets are forbidden")
    return value


def load_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("trusted remote-acquisition contract digest mismatch")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("artifact_id") != CONTRACT_ID:
        raise ValueError("trusted remote-acquisition contract identity mismatch")
    return payload


def freeze_binance_listobjects_request(
    *,
    prefix: str,
    continuation_token: str | None = None,
    predecessor_receipt_sha256: str | None = None,
) -> FrozenRequest:
    if not isinstance(prefix, str) or not prefix.startswith("data/spot/monthly/klines/"):
        raise ValueError("Binance prefix must stay under frozen spot/monthly/klines root")
    if ".." in prefix or "\\" in prefix or "\x00" in prefix:
        raise ValueError("Binance prefix contains forbidden path material")
    predecessor = _clean_sha256(
        predecessor_receipt_sha256, field="predecessor_receipt_sha256", optional=True
    )
    if continuation_token is not None:
        if not isinstance(continuation_token, str) or not continuation_token:
            raise ValueError("continuation_token must be non-empty when supplied")
        if len(continuation_token.encode("utf-8")) > 8192:
            raise ValueError("continuation_token is too large")
        if predecessor is None:
            raise ValueError("paginated Binance requests require predecessor receipt SHA-256")
    elif predecessor is not None:
        raise ValueError("predecessor receipt requires a continuation_token")

    query_items = [("list-type", "2"), ("prefix", prefix)]
    if continuation_token is not None:
        query_items.append(("continuation-token", continuation_token))
    query = urlencode(query_items)
    host = "s3-ap-northeast-1.amazonaws.com"
    target = f"/data.binance.vision?{query}"
    return FrozenRequest(
        source_kind="BINANCE_LISTOBJECTS_V2",
        method="GET",
        host=host,
        target=target,
        url=f"https://{host}{target}",
        predecessor_receipt_sha256=predecessor,
        max_response_bytes=MAX_BINANCE_BYTES,
    )


def freeze_commoncrawl_index_request(
    *, collection: str, target_url: str
) -> FrozenRequest:
    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError("Common Crawl collection must match CC-MAIN-YYYY-NN")
    target_url = _clean_https_url(target_url, field="target_url")
    host = "index.commoncrawl.org"
    query = urlencode([("url", target_url), ("output", "json")])
    target = f"/{collection}-index?{query}"
    return FrozenRequest(
        source_kind="COMMONCRAWL_INDEX",
        method="GET",
        host=host,
        target=target,
        url=f"https://{host}{target}",
        max_response_bytes=MAX_CC_INDEX_BYTES,
    )


def freeze_commoncrawl_warc_request(
    *, collection: str, filename: str, offset: int, length: int
) -> FrozenRequest:
    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError("Common Crawl collection must match CC-MAIN-YYYY-NN")
    if not isinstance(filename, str):
        raise ValueError("Common Crawl filename missing")
    match = WARC_FILENAME_RE.fullmatch(filename)
    if not match or match.group(1) != collection:
        raise ValueError("Common Crawl WARC filename/collection mismatch")
    path = PurePosixPath(filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Common Crawl WARC filename is unsafe")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("Common Crawl offset must be a nonnegative integer")
    if (
        not isinstance(length, int)
        or isinstance(length, bool)
        or length <= 0
        or length > MAX_CC_WARC_BYTES
    ):
        raise ValueError("Common Crawl length is outside frozen bound")
    host = "data.commoncrawl.org"
    target = "/" + quote(filename, safe="/._-")
    end = offset + length - 1
    return FrozenRequest(
        source_kind="COMMONCRAWL_WARC_RANGE",
        method="GET",
        host=host,
        target=target,
        url=f"https://{host}{target}",
        range_header=f"bytes={offset}-{end}",
        max_response_bytes=length,
    )


def _lower_headers(items: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in items:
        lower = key.strip().lower()
        if lower in result:
            result[lower] = result[lower] + ", " + value.strip()
        else:
            result[lower] = value.strip()
    return result


def fetch_once(request: FrozenRequest, *, timeout_seconds: float = 30.0) -> FetchResult:
    """Fetch once using direct TLS and never follow redirects."""
    if request.method != "GET":
        raise ValueError("only GET is supported")
    started_at = _utc_now()
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(
        request.host, 443, timeout=timeout_seconds, context=context
    )
    try:
        connection.request(request.method, request.target, headers=request.headers())
        response = connection.getresponse()
        status = int(response.status)
        headers = _lower_headers(response.getheaders())
        if status != 200 and not (
            request.source_kind == "COMMONCRAWL_WARC_RANGE" and status == 206
        ):
            response.read(min(request.max_response_bytes + 1, 65536))
            raise ValueError(f"provider returned non-authoritative HTTP status {status}")
        body = response.read(request.max_response_bytes + 1)
        if len(body) > request.max_response_bytes:
            raise ValueError("provider response exceeds frozen byte limit")
        if request.source_kind == "COMMONCRAWL_WARC_RANGE":
            if status != 206:
                raise ValueError("Common Crawl WARC range must return HTTP 206")
            if len(body) != request.max_response_bytes:
                raise ValueError("Common Crawl WARC range byte count mismatch")
            content_range = headers.get("content-range", "")
            expected_end = int(request.range_header.split("=")[1].split("-")[1])
            expected_start = int(request.range_header.split("=")[1].split("-")[0])
            expected = f"bytes {expected_start}-{expected_end}/"
            if not content_range.startswith(expected):
                raise ValueError("Common Crawl Content-Range does not match frozen range")
        elif status != 200:
            raise ValueError("non-range provider request must return HTTP 200")
    finally:
        connection.close()
    return FetchResult(
        status=status,
        headers=headers,
        body=body,
        started_at=started_at,
        completed_at=_utc_now(),
    )


def trusted_github_context(env: dict[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    repository = env.get("GITHUB_REPOSITORY")
    ref = env.get("GITHUB_REF")
    event = env.get("GITHUB_EVENT_NAME")
    sha = env.get("GITHUB_SHA")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF")
    run_id = env.get("GITHUB_RUN_ID")
    run_attempt = env.get("GITHUB_RUN_ATTEMPT")

    if repository != EXPECTED_REPOSITORY:
        raise ValueError("trusted acquisition must run in canonical repository")
    if ref != EXPECTED_REF:
        raise ValueError("trusted acquisition must run from canonical main")
    if event != EXPECTED_EVENT:
        raise ValueError("trusted acquisition must be workflow_dispatch")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("GITHUB_SHA must be a full commit SHA")
    if workflow_ref != EXPECTED_WORKFLOW_REF:
        raise ValueError(
            "GITHUB_WORKFLOW_REF must identify the exact trusted acquisition workflow on canonical main"
        )
    if not isinstance(run_id, str) or not run_id.isdigit() or int(run_id) <= 0:
        raise ValueError("GITHUB_RUN_ID must be positive")
    if not isinstance(run_attempt, str) or not run_attempt.isdigit() or int(run_attempt) <= 0:
        raise ValueError("GITHUB_RUN_ATTEMPT must be positive")
    return {
        "repository": repository,
        "git_sha": sha,
        "git_ref": ref,
        "workflow_ref": workflow_ref,
        "run_id": int(run_id),
        "run_attempt": int(run_attempt),
        "event_name": event,
    }


def canonical_receipt(
    request: FrozenRequest,
    result: FetchResult,
    *,
    github_context: dict[str, Any],
) -> dict[str, Any]:
    response_sha256 = hashlib.sha256(result.body).hexdigest()
    payload: dict[str, Any] = {
        "schema": "trusted_remote_acquisition_receipt.v1",
        "source_contract_id": CONTRACT_ID,
        "source_kind": request.source_kind,
        "request": {
            "method": request.method,
            "url": request.url,
            "range_header": request.range_header,
        },
        "response": {
            "status": result.status,
            "sha256": response_sha256,
            "byte_count": len(result.body),
            "content_type": result.headers.get("content-type"),
            "etag": result.headers.get("etag"),
            "last_modified": result.headers.get("last-modified"),
            "content_range": result.headers.get("content-range"),
        },
        "acquisition": {
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            **github_context,
        },
        "chain": {
            "predecessor_receipt_sha256": request.predecessor_receipt_sha256,
        },
        "authority": "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def verify_receipt_bytes(receipt: dict[str, Any], response_bytes: bytes) -> None:
    if not isinstance(receipt, dict) or receipt.get("schema") != "trusted_remote_acquisition_receipt.v1":
        raise ValueError("unexpected trusted acquisition receipt schema")
    if receipt.get("source_contract_id") != CONTRACT_ID:
        raise ValueError("unexpected trusted acquisition contract")
    response = receipt.get("response")
    if not isinstance(response, dict):
        raise ValueError("receipt response block missing")
    if response.get("sha256") != hashlib.sha256(response_bytes).hexdigest():
        raise ValueError("retained response bytes do not match trusted receipt")
    if response.get("byte_count") != len(response_bytes):
        raise ValueError("retained response byte count does not match trusted receipt")
    stored = receipt.get("receipt_sha256")
    _clean_sha256(stored, field="receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != stored:
        raise ValueError("trusted acquisition receipt fingerprint mismatch")


def write_bundle(
    request: FrozenRequest,
    result: FetchResult,
    *,
    output_dir: str | Path,
    github_context: dict[str, Any],
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    response_path = out / "response.bin"
    receipt_path = out / "receipt.json"
    bundle_path = out / "trusted-acquisition.tar"
    response_path.write_bytes(result.body)
    receipt = canonical_receipt(request, result, github_context=github_context)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verify_receipt_bytes(receipt, response_path.read_bytes())

    with tarfile.open(bundle_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path, arcname in ((receipt_path, "receipt.json"), (response_path, "response.bin")):
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return {
        "receipt": receipt,
        "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        "bundle_path": str(bundle_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("BINANCE_LISTOBJECTS_V2", "COMMONCRAWL_INDEX", "COMMONCRAWL_WARC_RANGE"),
    )
    parser.add_argument("--prefix")
    parser.add_argument("--continuation-token")
    parser.add_argument("--predecessor-receipt-sha256")
    parser.add_argument("--collection")
    parser.add_argument("--target-url")
    parser.add_argument("--filename")
    parser.add_argument("--offset", type=int)
    parser.add_argument("--length", type=int)
    parser.add_argument("--output-dir", default="trusted-acquisition-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_contract()
    if args.source_kind == "BINANCE_LISTOBJECTS_V2":
        request = freeze_binance_listobjects_request(
            prefix=args.prefix or "",
            continuation_token=args.continuation_token,
            predecessor_receipt_sha256=args.predecessor_receipt_sha256,
        )
    elif args.source_kind == "COMMONCRAWL_INDEX":
        request = freeze_commoncrawl_index_request(
            collection=args.collection or "", target_url=args.target_url or ""
        )
    else:
        if args.offset is None or args.length is None:
            raise ValueError("Common Crawl WARC range requires offset and length")
        request = freeze_commoncrawl_warc_request(
            collection=args.collection or "",
            filename=args.filename or "",
            offset=args.offset,
            length=args.length,
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

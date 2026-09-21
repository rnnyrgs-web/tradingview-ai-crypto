"""Outcome-blind historical Binance spot/USDT universe discovery for 2x Cohort 001.

The historical cohort must not begin from today's surviving exchange symbols. Every
listing page consumed here must first pass the shared #542 GitHub-attestation verifier;
a local XML file, local digest and official-looking URL have zero universe authority.

Archive presence is intentionally narrow authority: it is useful for survivorship-safe
universe discovery only. It does not prove listing age, liquidity/tradability, a 2x
outcome, a forecast candidate, or any trading permission.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from defusedxml import ElementTree as ET

from trusted_remote_acquisition_consumer import verify_attested_acquisition_bundle

CONTRACT_PATH = "money_intelligence/2x_binance_historical_universe_contract_v1.json"
CONTRACT_ARTIFACT_ID = "2X-BINANCE-HISTORICAL-UNIVERSE-001-v1"
CONTRACT_GIT_BLOB_SHA = "582bff3b9f19ad2c21e134b68090d61158fda102"
EXPECTED_PREFIX = "data/spot/monthly/klines/"
EXPECTED_HOST = "s3-ap-northeast-1.amazonaws.com"
EXPECTED_BUCKET_PATH = "/data.binance.vision"
EXPECTED_BUCKET_NAME = "data.binance.vision"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OBJECT_RE = re.compile(
    r"^data/spot/monthly/klines/([^/\r\n]{1,64}USDT)/1d/"
    r"\1-1d-(\d{4})-(\d{2})\.zip(?P<checksum>\.CHECKSUM)?$"
)
FORBIDDEN_KEYS = {
    "2x",
    "winner",
    "label",
    "outcome",
    "future_return",
    "max_forward_return",
    "selected_after_outcome",
}


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("historical-universe contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("historical-universe contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("historical-universe contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected canonical historical-universe contract identity")
    if contract.get("source") != {
        "provider": "BINANCE_PUBLIC_DATA",
        "download_host": "data.binance.vision",
        "listing_host": EXPECTED_HOST,
        "listing_bucket_path": EXPECTED_BUCKET_PATH,
        "listing_bucket_name": EXPECTED_BUCKET_NAME,
        "archive_family": "data/spot/monthly/klines/<SYMBOL>/1d/<SYMBOL>-1d-YYYY-MM.zip",
        "checksum_suffix": ".CHECKSUM",
        "quote_asset": "USDT",
    }:
        raise ValueError("historical-universe source contract drifted")
    return contract


def _reject_forbidden_keys(value: Any, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.casefold() in FORBIDDEN_KEYS:
                raise ValueError(f"outcome-derived field forbidden in historical universe input: {path}.{key}")
            _reject_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, path=f"{path}[{index}]")


def _safe_bundle_path(root: Path, relpath: Any, *, field: str) -> Path:
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.bundle_relpath missing")
    relative = Path(relpath)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field}.bundle_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.bundle_relpath escapes retained artifact root")
    return path


def _request_token(locator: Any, *, field: str) -> str | None:
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError(f"{field}.request.url missing")
    parts = urlsplit(locator)
    if (
        parts.scheme != "https"
        or parts.hostname != EXPECTED_HOST
        or parts.path != EXPECTED_BUCKET_PATH
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError(
            f"{field}.request.url must use clean HTTPS on {EXPECTED_HOST}{EXPECTED_BUCKET_PATH}"
        )
    query = parse_qs(parts.query, keep_blank_values=True)
    if set(query) - {"list-type", "prefix", "continuation-token"}:
        raise ValueError(f"{field}.request.url contains unsupported query parameters")
    if query.get("list-type") != ["2"]:
        raise ValueError(f"{field}.request.url must use S3 ListObjectsV2 list-type=2")
    if query.get("prefix") != [EXPECTED_PREFIX]:
        raise ValueError(f"{field}.request.url prefix mismatch")
    tokens = query.get("continuation-token")
    if tokens is None:
        return None
    if len(tokens) != 1 or not tokens[0]:
        raise ValueError(f"{field}.request.url continuation-token malformed")
    return tokens[0]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(root: ET.Element, name: str) -> str | None:
    for child in list(root):
        if _local_name(child.tag) == name:
            return child.text or ""
    return None


def _contents_keys(root: ET.Element) -> list[str]:
    keys: list[str] = []
    for child in list(root):
        if _local_name(child.tag) != "Contents":
            continue
        key = _child_text(child, "Key")
        if not key:
            raise ValueError("Binance listing Contents row missing Key")
        keys.append(key)
    return keys


def _parse_listing(raw: bytes, *, field: str, request_token: str | None) -> dict[str, Any]:
    try:
        xml_root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"{field} is not valid XML") from exc
    if _local_name(xml_root.tag) != "ListBucketResult":
        raise ValueError(f"{field} must be an S3 ListBucketResult")
    if _child_text(xml_root, "Name") != EXPECTED_BUCKET_NAME:
        raise ValueError(f"{field} bucket Name does not match frozen provider bucket")
    if _child_text(xml_root, "Prefix") != EXPECTED_PREFIX:
        raise ValueError(f"{field} Prefix does not match frozen archive prefix")
    response_token = _child_text(xml_root, "ContinuationToken") or None
    if response_token != request_token:
        raise ValueError(f"{field} response ContinuationToken does not match authenticated request")
    truncated_text = (_child_text(xml_root, "IsTruncated") or "").strip().lower()
    if truncated_text not in {"true", "false"}:
        raise ValueError(f"{field} IsTruncated must be true or false")
    truncated = truncated_text == "true"
    next_token = _child_text(xml_root, "NextContinuationToken") or None
    if truncated and not next_token:
        raise ValueError(f"{field} truncated page missing NextContinuationToken")
    if not truncated and next_token:
        raise ValueError(f"{field} terminal page must not advertise a continuation token")
    if next_token is not None and next_token == request_token:
        raise ValueError(f"{field} provider continuation token did not advance")
    return {"is_truncated": truncated, "next_token": next_token, "keys": _contents_keys(xml_root)}


def _month_key(year_text: str, month_text: str) -> str:
    year = int(year_text)
    month = int(month_text)
    try:
        date(year, month, 1)
    except ValueError as exc:
        raise ValueError("Binance archive object contains invalid year-month") from exc
    return f"{year:04d}-{month:02d}"


def build_historical_universe(
    pages: list[dict[str, Any]],
    *,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a universe only from a complete attestation-verified S3 prefix walk."""
    contract = load_contract(repo_root)
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a non-empty list")
    _reject_forbidden_keys(pages)
    root = Path(artifact_root)

    expected_token: str | None = None
    expected_predecessor_receipt: str | None = None
    request_locators: set[str] = set()
    response_shas: set[str] = set()
    receipt_shas: set[str] = set()
    object_keys: set[str] = set()
    archive_parts: dict[tuple[str, str], set[str]] = defaultdict(set)
    page_receipts: list[dict[str, Any]] = []

    for index, ref in enumerate(pages):
        field = f"pages[{index}]"
        if not isinstance(ref, dict):
            raise ValueError(f"{field} must be an object")
        allowed = {"bundle_relpath"}
        extra = set(ref) - allowed
        if extra:
            raise ValueError(f"{field} contains unsupported fields: {sorted(extra)}")
        bundle_path = _safe_bundle_path(root, ref.get("bundle_relpath"), field=field)
        receipt, raw = verify_attested_acquisition_bundle(
            bundle_path,
            expected_source_kind="BINANCE_LISTOBJECTS_V2",
        )
        request = receipt.get("request")
        chain = receipt.get("chain")
        response = receipt.get("response")
        if not isinstance(request, dict) or request.get("method") != "GET" or request.get("range_header") is not None:
            raise ValueError(f"{field} trusted request must be a non-range GET")
        if not isinstance(chain, dict):
            raise ValueError(f"{field} trusted receipt chain block missing")
        if not isinstance(response, dict):
            raise ValueError(f"{field} trusted receipt response block missing")
        request_locator = request.get("url")
        request_token = _request_token(request_locator, field=field)
        if request_token != expected_token:
            raise ValueError(f"{field} continuation-token does not match prior provider page")
        predecessor = chain.get("predecessor_receipt_sha256")
        if predecessor != expected_predecessor_receipt:
            raise ValueError(f"{field} trusted receipt predecessor chain mismatch")

        receipt_sha = receipt.get("receipt_sha256")
        response_sha = response.get("sha256")
        if not isinstance(receipt_sha, str) or not SHA256_RE.fullmatch(receipt_sha):
            raise ValueError(f"{field} trusted receipt SHA-256 malformed")
        if not isinstance(response_sha, str) or not SHA256_RE.fullmatch(response_sha):
            raise ValueError(f"{field} trusted response SHA-256 malformed")
        if request_locator in request_locators:
            raise ValueError("duplicate Binance listing request locator")
        if receipt_sha in receipt_shas:
            raise ValueError("duplicate trusted Binance listing receipt")
        if response_sha in response_shas:
            raise ValueError("duplicate authenticated Binance listing page bytes")
        request_locators.add(request_locator)
        receipt_shas.add(receipt_sha)
        response_shas.add(response_sha)

        parsed = _parse_listing(raw, field=field, request_token=request_token)
        for key in parsed["keys"]:
            if key in object_keys:
                raise ValueError("duplicate Binance archive object key across listing pages")
            object_keys.add(key)
            match = OBJECT_RE.fullmatch(key)
            if match is None:
                continue
            symbol, year_text, month_text = match.group(1), match.group(2), match.group(3)
            month = _month_key(year_text, month_text)
            archive_parts[(symbol, month)].add("checksum" if match.group("checksum") else "zip")

        acquisition = receipt.get("acquisition")
        page_receipts.append(
            {
                "page_index": index,
                "request_locator": request_locator,
                "trusted_receipt_sha256": receipt_sha,
                "response_sha256": response_sha,
                "acquisition_git_sha": acquisition.get("git_sha") if isinstance(acquisition, dict) else None,
                "acquisition_run_id": acquisition.get("run_id") if isinstance(acquisition, dict) else None,
                "object_key_count": len(parsed["keys"]),
                "is_truncated": parsed["is_truncated"],
            }
        )
        expected_predecessor_receipt = receipt_sha
        expected_token = parsed["next_token"]
        if not parsed["is_truncated"]:
            if index != len(pages) - 1:
                raise ValueError("pages continue after terminal Binance listing page")
            expected_token = None
        elif index == len(pages) - 1:
            raise ValueError("incomplete Binance listing prefix walk")

    if expected_token is not None:
        raise ValueError("incomplete Binance listing prefix walk")

    paired_months: dict[str, list[str]] = defaultdict(list)
    incomplete_pairs: list[dict[str, str]] = []
    for (symbol, month), parts in sorted(archive_parts.items()):
        if parts == {"zip", "checksum"}:
            paired_months[symbol].append(month)
        else:
            incomplete_pairs.append({"symbol": symbol, "month": month, "present": ",".join(sorted(parts))})
    if incomplete_pairs:
        raise ValueError("Binance archive zip/checksum pairing is incomplete")
    if not paired_months:
        raise ValueError("complete listing contains no paired spot/USDT monthly 1d archives")

    universe: list[dict[str, Any]] = []
    for symbol in sorted(paired_months):
        months = sorted(set(paired_months[symbol]))
        universe.append(
            {
                "symbol": symbol,
                "quote_asset": "USDT",
                "first_archive_month": months[0],
                "last_archive_month": months[-1],
                "archive_month_count": len(months),
                "archive_months": months,
                "membership_authority": "ARCHIVE_PRESENCE_ONLY_NOT_LISTING_AGE_OR_TRADABILITY",
            }
        )

    result: dict[str, Any] = {
        "schema": "two_x_binance_historical_universe.v1",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "contract_git_blob_sha": CONTRACT_GIT_BLOB_SHA,
        "source_provider": contract["source"]["provider"],
        "source_prefix": EXPECTED_PREFIX,
        "provider_origin_authentication": "GITHUB_ATTESTED_TRUSTED_ACQUISITION_REQUIRED",
        "page_count": len(page_receipts),
        "page_receipts": page_receipts,
        "symbol_count": len(universe),
        "symbols": universe,
        "survivorship_policy": "INCLUDES_ARCHIVED_DELISTED_SYMBOLS_DOES_NOT_USE_CURRENT_EXCHANGE_INFO",
        "outcome_access": "SEALED",
        "label_authority": False,
        "forecast_authority": False,
        "trade_authority": False,
        "output_authority": contract["output_authority"],
    }
    result["result_digest_sha256"] = _canonical_digest(result)
    return result

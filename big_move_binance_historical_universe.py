"""Outcome-blind historical Binance spot/USDT universe discovery for 2x Cohort 001.

The historical cohort must not begin from today's surviving exchange symbols. This
module consumes retained, checksum-addressed provider bucket-listing XML pages for the
Binance monthly spot 1d archive and derives archive-presence intervals for every USDT
symbol it observes, including symbols that later disappeared.

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
import xml.etree.ElementTree as ET

CONTRACT_PATH = "money_intelligence/2x_binance_historical_universe_contract_v1.json"
CONTRACT_ARTIFACT_ID = "2X-BINANCE-HISTORICAL-UNIVERSE-001-v1"
CONTRACT_GIT_BLOB_SHA = "7e55fd09a4af2aca5faa5bfc020e72cc8f2f8042"
EXPECTED_PREFIX = "data/spot/monthly/klines/"
EXPECTED_HOST = "data.binance.vision"
MAX_PAGE_BYTES = 16 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OBJECT_RE = re.compile(
    r"^data/spot/monthly/klines/([A-Z0-9]{2,24}USDT)/1d/"
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
        raise ValueError("unexpected historical-universe contract identity")
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


def _safe_path(root: Path, relpath: Any, *, field: str) -> Path:
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.artifact_relpath missing")
    relative = Path(relpath)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field}.artifact_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.artifact_relpath escapes retained artifact root")
    return path


def _verified_page_bytes(root: Path, ref: dict[str, Any], *, field: str) -> bytes:
    sha256 = ref.get("sha256")
    if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    path = _safe_path(root, ref.get("artifact_relpath"), field=field)
    try:
        if path.stat().st_size > MAX_PAGE_BYTES:
            raise ValueError(f"{field} exceeds retained-page size limit")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained page is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{field} retained page SHA-256 mismatch")
    return raw


def _request_token(locator: Any, *, field: str) -> str | None:
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError(f"{field}.request_locator missing")
    parts = urlsplit(locator)
    if (
        parts.scheme != "https"
        or parts.hostname != EXPECTED_HOST
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError(f"{field}.request_locator must use clean HTTPS on {EXPECTED_HOST}")
    query = parse_qs(parts.query, keep_blank_values=True)
    if query.get("list-type") != ["2"]:
        raise ValueError(f"{field}.request_locator must use S3 ListObjectsV2 list-type=2")
    if query.get("prefix") != [EXPECTED_PREFIX]:
        raise ValueError(f"{field}.request_locator prefix mismatch")
    tokens = query.get("continuation-token")
    if tokens is None:
        return None
    if len(tokens) != 1 or not tokens[0]:
        raise ValueError(f"{field}.request_locator continuation-token malformed")
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


def _parse_listing(raw: bytes, *, field: str) -> dict[str, Any]:
    try:
        xml_root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"{field} is not valid XML") from exc
    if _local_name(xml_root.tag) != "ListBucketResult":
        raise ValueError(f"{field} must be an S3 ListBucketResult")
    prefix = _child_text(xml_root, "Prefix")
    if prefix != EXPECTED_PREFIX:
        raise ValueError(f"{field} Prefix does not match frozen archive prefix")
    truncated_text = (_child_text(xml_root, "IsTruncated") or "").strip().lower()
    if truncated_text not in {"true", "false"}:
        raise ValueError(f"{field} IsTruncated must be true or false")
    truncated = truncated_text == "true"
    next_token = _child_text(xml_root, "NextContinuationToken")
    if truncated and not next_token:
        raise ValueError(f"{field} truncated page missing NextContinuationToken")
    if not truncated and next_token:
        raise ValueError(f"{field} terminal page must not advertise a continuation token")
    return {
        "is_truncated": truncated,
        "next_token": next_token or None,
        "keys": _contents_keys(xml_root),
    }


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
    """Build an outcome-blind archive-presence universe from a complete S3 prefix walk."""

    contract = load_contract(repo_root)
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a non-empty list")
    _reject_forbidden_keys(pages)
    root = Path(artifact_root)

    expected_token: str | None = None
    page_identities: set[tuple[str, str]] = set()
    object_keys: set[str] = set()
    archive_parts: dict[tuple[str, str], set[str]] = defaultdict(set)
    page_receipts: list[dict[str, Any]] = []

    for index, ref in enumerate(pages):
        field = f"pages[{index}]"
        if not isinstance(ref, dict):
            raise ValueError(f"{field} must be an object")
        allowed = {"artifact_relpath", "sha256", "request_locator"}
        extra = set(ref) - allowed
        if extra:
            raise ValueError(f"{field} contains unsupported fields: {sorted(extra)}")
        request_token = _request_token(ref.get("request_locator"), field=field)
        if request_token != expected_token:
            raise ValueError(f"{field} continuation-token does not match prior provider page")
        raw = _verified_page_bytes(root, ref, field=field)
        identity = (ref["request_locator"], ref["sha256"])
        if identity in page_identities:
            raise ValueError("duplicate retained Binance listing page identity")
        page_identities.add(identity)
        parsed = _parse_listing(raw, field=field)

        for key in parsed["keys"]:
            if key in object_keys:
                raise ValueError("duplicate Binance archive object key across listing pages")
            object_keys.add(key)
            match = OBJECT_RE.fullmatch(key)
            if match is None:
                continue
            symbol, year_text, month_text = match.group(1), match.group(2), match.group(3)
            month = _month_key(year_text, month_text)
            part = "checksum" if match.group("checksum") else "zip"
            archive_parts[(symbol, month)].add(part)

        page_receipts.append({
            "page_index": index,
            "request_locator": ref["request_locator"],
            "sha256": ref["sha256"],
            "object_key_count": len(parsed["keys"]),
            "is_truncated": parsed["is_truncated"],
        })
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
        universe.append({
            "symbol": symbol,
            "quote_asset": "USDT",
            "first_archive_month": months[0],
            "last_archive_month": months[-1],
            "archive_month_count": len(months),
            "archive_months": months,
            "membership_authority": "ARCHIVE_PRESENCE_ONLY_NOT_LISTING_AGE_OR_TRADABILITY",
        })

    result: dict[str, Any] = {
        "schema": "two_x_binance_historical_universe.v1",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "contract_git_blob_sha": CONTRACT_GIT_BLOB_SHA,
        "source_provider": contract["source"]["provider"],
        "source_prefix": EXPECTED_PREFIX,
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

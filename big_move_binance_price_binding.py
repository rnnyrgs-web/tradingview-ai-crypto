"""Exact direct-price binding for 2x Cohort 001 Binance evidence.

A checksum-authenticated archive proves where bytes came from, but a normalized
`price` field must also be mechanically reproduced from those exact bytes.  This
module freezes the authoritative v1 rule before any 2x outcome labels are opened:
the decision price is the close of the latest completed UTC 1d Binance spot kline
strictly before `decision_at`.

This is evidence validation only.  It cannot open outcomes, form a forecast, or
grant prediction/trading authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from big_move_binance_archive_binding import (
    parse_spot_1d_kline_archive,
    verify_checksum_sidecar,
)

UTC = timezone.utc
SOURCE_ID = "BINANCE_PUBLIC_DATA_SPOT_RAW"
CONTRACT_PATH = "money_intelligence/2x_binance_price_binding_v1.json"
CONTRACT_ARTIFACT_ID = "2X-BINANCE-PRICE-BINDING-001-v1"
CONTRACT_GIT_BLOB_SHA = "4f3102befe5a1e6d9a53397f791468a8a2e0d067"
FULL_ARCHIVE_CUTOFF = "9999-01-01T00:00:00Z"
MAX_RETAINED_BYTES = 128 * 1024 * 1024
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,24}USDT$")


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


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


def _retained_bytes(root: Path, relpath: Any, sha256: Any, *, field: str) -> bytes:
    if not isinstance(sha256, str) or len(sha256) != 64 or sha256.lower() != sha256:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    try:
        int(sha256, 16)
    except ValueError as exc:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256") from exc
    path = _safe_path(root, relpath, field=field)
    try:
        if path.stat().st_size > MAX_RETAINED_BYTES:
            raise ValueError(f"{field} retained artifact is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    return raw


def _retained_json(root: Path, ref: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} reference missing")
    raw = _retained_bytes(
        root,
        ref.get("artifact_relpath"),
        ref.get("sha256"),
        field=field,
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field} must contain JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return value


def load_price_binding_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("Binance price-binding contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("Binance price-binding contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Binance price-binding contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected Binance price-binding contract identity")
    return contract


def _validate_locator(locator: Any, *, venue_symbol: str) -> str:
    if not isinstance(locator, str) or not locator:
        raise ValueError("Binance price proof upstream_locator missing")
    parsed = urlsplit(locator)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Binance price proof locator must be clean official HTTPS archive URL")
    parts = [part for part in parsed.path.split("/") if part]
    try:
        spot_index = parts.index("spot")
    except ValueError as exc:
        raise ValueError("Binance price proof locator is not a spot archive") from exc
    expected_tail_prefixes = [
        ["daily", "klines", venue_symbol, "1d"],
        ["monthly", "klines", venue_symbol, "1d"],
    ]
    tail = parts[spot_index + 1 : spot_index + 5]
    if tail not in expected_tail_prefixes:
        raise ValueError("Binance price proof locator does not bind symbol and 1d kline interval")
    archive_name = parts[-1] if parts else ""
    if not archive_name.endswith(".zip"):
        raise ValueError("Binance price proof locator must identify a ZIP archive")
    return archive_name


def _decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{field} must be a positive decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be a positive decimal")
    return parsed


def validate_binance_decision_price(
    record: dict[str, Any],
    *,
    venue_symbol: str,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Bind one normalized decision-price record to official retained 1d kline bytes."""
    load_price_binding_contract(repo_root)
    if not isinstance(record, dict) or record.get("source_id") != SOURCE_ID:
        raise ValueError("price must use BINANCE_PUBLIC_DATA_SPOT_RAW")
    if not isinstance(venue_symbol, str) or SYMBOL_RE.fullmatch(venue_symbol) is None:
        raise ValueError("venue_symbol must be a Binance USDT spot symbol")
    decision = _utc(decision_at, field="decision_at")
    root = Path(artifact_root)

    proof = _retained_json(root, record.get("source_proof"), field="price.source_proof")
    if proof.get("schema") != "binance_public_archive_proof.v1" or proof.get("source_id") != SOURCE_ID:
        raise ValueError("price requires matching binance_public_archive_proof.v1")
    archive_name = _validate_locator(proof.get("upstream_locator"), venue_symbol=venue_symbol)

    archive_bytes = _retained_bytes(
        root,
        proof.get("archive_relpath"),
        proof.get("archive_sha256"),
        field="price.archive",
    )
    checksum_bytes = _retained_bytes(
        root,
        proof.get("checksum_relpath"),
        proof.get("checksum_sha256"),
        field="price.checksum",
    )
    archive_sha = verify_checksum_sidecar(archive_bytes, checksum_bytes, archive_name)

    # Parse the complete retained archive first.  A proof may not lie about the
    # archive's true latest event timestamp in order to hide post-decision rows.
    all_rows = parse_spot_1d_kline_archive(
        archive_bytes,
        decision_at=FULL_ARCHIVE_CUTOFF,
    )
    if not all_rows:
        raise ValueError("Binance price archive contains no 1d kline rows")
    latest_archive = all_rows[-1]
    latest_archive_close = _utc(latest_archive["close_time"], field="archive.latest_close_time")
    if latest_archive_close >= decision:
        raise ValueError("Binance price archive contains a post-decision or incomplete bar")

    proof_event_max = _utc(proof.get("event_time_max"), field="price.proof.event_time_max")
    if proof_event_max != latest_archive_close:
        raise ValueError("Binance price proof event_time_max does not match retained archive bytes")

    eligible = parse_spot_1d_kline_archive(archive_bytes, decision_at=decision_at)
    if not eligible:
        raise ValueError("Binance price archive has no completed pre-decision 1d bar")
    latest = eligible[-1]
    latest_close_time = _utc(latest["close_time"], field="price.latest_close_time")
    if latest_close_time != latest_archive_close:
        raise ValueError("Binance price archive latest bar identity is inconsistent")

    if _decimal(record.get("value"), field="price.value") != _decimal(latest["close"], field="archive.close"):
        raise ValueError("price value does not match latest completed retained Binance close")
    observed_at = _utc(record.get("observed_at"), field="price.observed_at")
    if observed_at != latest_close_time:
        raise ValueError("price observed_at does not match latest completed retained Binance close_time")
    available_at = _utc(record.get("available_at"), field="price.available_at")
    if available_at < observed_at or available_at > decision:
        raise ValueError("price available_at is inconsistent with PIT chronology")

    return {
        "schema": "two_x_binance_price_binding_result.v1",
        "status": "BOUND",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "venue_symbol": venue_symbol,
        "decision_at": decision_at,
        "price": str(_decimal(latest["close"], field="archive.close")),
        "observed_at": latest["close_time"],
        "archive_sha256": archive_sha,
        "authority": "EVIDENCE_ONLY_NO_OUTCOME_OR_FORECAST_AUTHORITY",
    }

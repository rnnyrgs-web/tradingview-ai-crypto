"""Mechanical primary-document claim binding for 2x Cohort 001.

The generic source-authenticity layer verifies retained bytes, locator and PIT
publication/effective timestamps.  It must not, however, trust a caller-authored
`claim_value` field as proof that the retained document actually contains the claim.
This module binds the normalized evidence value to literal text derived from the exact
retained document bytes under a frozen, Git-blob-pinned normalization contract.

This deliberately performs no semantic inference. Sector classification remains a
separate frozen transform and stays blocked until implemented. Unsupported media or
non-literal claims fail closed rather than being hand-waved into coverage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any
import unicodedata
from urllib.parse import urlsplit

UTC = timezone.utc
CONTRACT_PATH = "money_intelligence/2x_primary_document_claim_binding_v1.json"
CONTRACT_ARTIFACT_ID = "2X-PRIMARY-DOCUMENT-CLAIM-BINDING-001-v1"
CONTRACT_GIT_BLOB_SHA = "79fd450ac8404daf225205c209950ed46a998661"
ELIGIBLE_SOURCE_IDS = {
    "PRIMARY_CONTRACT_OR_GENESIS_DOC",
    "TIMESTAMPED_PRIMARY_SUPPLY_DISCLOSURE",
}
MAX_RETAINED_BYTES = 16 * 1024 * 1024


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._suppressed_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._suppressed_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._suppressed_depth:
            self._suppressed_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self.parts.append(data)


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
    raw = _retained_bytes(root, ref.get("artifact_relpath"), ref.get("sha256"), field=field)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field} must contain JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return value


def load_primary_claim_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("primary-document claim-binding contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("primary-document claim-binding contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("primary-document claim-binding contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected primary-document claim-binding contract identity")
    return contract


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def _visible_text(document: bytes, media_type: Any) -> str:
    if media_type not in {"text/plain", "text/html"}:
        raise ValueError("primary document media_type is unsupported")
    try:
        decoded = document.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("primary document must be strict UTF-8") from exc
    if media_type == "text/plain":
        return decoded
    parser = _VisibleTextParser()
    try:
        parser.feed(decoded)
        parser.close()
    except Exception as exc:  # HTMLParser can surface malformed entity/state errors.
        raise ValueError("primary HTML document could not be parsed deterministically") from exc
    return " ".join(parser.parts)


def _claim_string(value: Any) -> str:
    if value is None or isinstance(value, (bool, dict, list, tuple, set)):
        raise ValueError("primary-document claim must be a scalar string/number")
    claim = _normalize_text(str(value))
    if not claim:
        raise ValueError("primary-document claim is empty")
    return claim


def validate_primary_document_literal_claim(
    record: dict[str, Any],
    *,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Prove the evidence value occurs literally in the exact retained document text."""
    load_primary_claim_contract(repo_root)
    if not isinstance(record, dict) or record.get("source_id") not in ELIGIBLE_SOURCE_IDS:
        raise ValueError("record is not an eligible primary-document source")
    decision = _utc(decision_at, field="decision_at")
    root = Path(artifact_root)
    proof = _retained_json(root, record.get("source_proof"), field="primary.source_proof")
    if proof.get("schema") != "primary_document_proof.v1":
        raise ValueError("primary source requires primary_document_proof.v1")
    if proof.get("source_id") != record.get("source_id"):
        raise ValueError("primary proof source_id does not match record")

    locator = proof.get("upstream_locator")
    if not isinstance(locator, str) or not locator:
        raise ValueError("primary proof upstream_locator missing")
    parsed = urlsplit(locator)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("primary proof upstream_locator must be a clean HTTPS URL")

    published_at = _utc(proof.get("published_at"), field="primary.published_at")
    effective_raw = proof.get("effective_at")
    effective_at = _utc(effective_raw, field="primary.effective_at") if effective_raw is not None else published_at
    if published_at > decision or effective_at > decision:
        raise ValueError("primary document was not published/effective by decision_at")

    document = _retained_bytes(
        root,
        proof.get("document_relpath"),
        proof.get("document_sha256"),
        field="primary.document",
    )
    normalized_document = _normalize_text(_visible_text(document, proof.get("media_type")))
    claim = _claim_string(record.get("value"))
    # Token boundaries stop short identifiers such as L1 or SOL from matching inside
    # unrelated longer words. Multiple literal occurrences are acceptable because no
    # semantic inference is made from count or location.
    pattern = re.compile(r"(?<!\w)" + re.escape(claim) + r"(?!\w)")
    occurrences = len(pattern.findall(normalized_document))
    if occurrences < 1:
        raise ValueError("primary-document claim is not present in retained document bytes")

    return {
        "schema": "two_x_primary_document_claim_binding_result.v1",
        "status": "BOUND",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "source_id": record.get("source_id"),
        "claim": claim,
        "literal_occurrences": occurrences,
        "document_sha256": proof.get("document_sha256"),
        "published_at": proof.get("published_at"),
        "effective_at": proof.get("effective_at"),
        "authority": "EVIDENCE_ONLY_NO_SEMANTIC_OR_OUTCOME_AUTHORITY",
    }


def load_retained_record(ref: dict[str, Any], *, artifact_root: str | Path, field: str) -> dict[str, Any]:
    """Load a SHA-bound retained JSON evidence record for canonical traversal."""
    return _retained_json(Path(artifact_root), ref, field=field)

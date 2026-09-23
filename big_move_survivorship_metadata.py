"""Fail-closed survivorship metadata enumeration for the <=90-day 2x research lane.

This module uses retained Tardis Binance exchange-details metadata only to enumerate
historical instrument IDs that must not be silently dropped from later Cohort-001
identity work. It grants no historical-membership, delisting-time, outcome, control,
model, candidate, broker, or trading authority.

Important semantic boundary:
- ``availableSince`` / ``availableTo`` are Tardis data-collection coverage bounds;
- ``availableTo`` is NOT an authenticated exchange delisting timestamp;
- current ``active`` state, if present in a provider response, is ignored for historical
  membership so today's survivors cannot define the historical universe;
- duplicate/reused symbol IDs fail closed until an external timestamp-safe identity
  resolver proves which asset identity applies to each interval;
- the retained provider response SHA-256 is recomputed from the exact raw bytes before
  parsing. A caller-supplied digest cannot authenticate a different parsed payload;
- duplicate JSON object keys and non-standard JSON numeric constants fail closed so one
  retained byte stream cannot have parser-dependent semantics;
- ``captured_at`` is chronology metadata only unless a separate trusted capture receipt
  authenticates it. It is never historical availability proof by itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

CONTRACT_ID = "2X-SURVIVORSHIP-METADATA-ENUMERATION-001-v1"
OUTPUT_SCHEMA = "2X-SURVIVORSHIP-ENUMERATION-MANIFEST-001-v1"
SOURCE_ID = "TARDIS_EXCHANGE_DETAILS_BINANCE"
VENUE = "BINANCE_SPOT"
EXCHANGE_ID = "binance"
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,24}USDT$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GROUPED_IDS = {"SPOT", "FUTURES", "PERPETUALS", "OPTIONS"}


class SurvivorshipMetadataError(ValueError):
    """Raised when provider metadata cannot be safely used for enumeration."""


def _utc(value: Any, *, field: str, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SurvivorshipMetadataError(f"{field} must be a non-empty RFC3339 UTC timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SurvivorshipMetadataError(f"{field} must be valid RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise SurvivorshipMetadataError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _source_sha(value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise SurvivorshipMetadataError("expected_source_response_sha256 must be lowercase SHA-256")
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SurvivorshipMetadataError(f"provider response JSON contains duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> Any:
    raise SurvivorshipMetadataError(f"provider response JSON contains non-standard numeric constant {value}")


def _authenticated_provider_payload(
    provider_response_bytes: Any,
    *,
    expected_source_response_sha256: str,
) -> tuple[dict[str, Any], str]:
    """Authenticate exact retained bytes before interpreting provider metadata."""

    if not isinstance(provider_response_bytes, bytes) or not provider_response_bytes:
        raise SurvivorshipMetadataError("provider_response_bytes must be non-empty exact retained bytes")
    expected = _source_sha(expected_source_response_sha256)
    actual = hashlib.sha256(provider_response_bytes).hexdigest()
    if actual != expected:
        raise SurvivorshipMetadataError("provider response bytes do not match expected SHA-256")
    try:
        response_text = provider_response_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SurvivorshipMetadataError("provider response bytes must be valid UTF-8 JSON") from exc
    try:
        payload = json.loads(
            response_text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise SurvivorshipMetadataError("provider response bytes must contain valid JSON") from exc
    if not isinstance(payload, dict):
        raise SurvivorshipMetadataError("provider response JSON must be an object")
    return payload, actual


def _symbol_records(provider_payload: dict[str, Any]) -> list[dict[str, Any]]:
    if provider_payload.get("id") != EXCHANGE_ID:
        raise SurvivorshipMetadataError(f"provider payload id must be {EXCHANGE_ID}")
    datasets = provider_payload.get("datasets")
    if not isinstance(datasets, dict):
        raise SurvivorshipMetadataError("provider payload datasets must be an object")
    symbols = datasets.get("symbols")
    if not isinstance(symbols, list):
        raise SurvivorshipMetadataError("provider payload datasets.symbols must be a list")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(symbols):
        if not isinstance(item, dict):
            raise SurvivorshipMetadataError(f"datasets.symbols[{index}] must be an object")
        symbol = item.get("id")
        if not isinstance(symbol, str) or not symbol.strip():
            raise SurvivorshipMetadataError(f"datasets.symbols[{index}].id must be non-empty")
        symbol = symbol.strip().upper()
        if symbol in GROUPED_IDS or SYMBOL_RE.fullmatch(symbol) is None:
            continue
        if symbol in seen:
            raise SurvivorshipMetadataError(
                f"duplicate/reused symbol id {symbol} requires timestamp-safe external identity resolution"
            )
        seen.add(symbol)

        data_types = item.get("dataTypes")
        if not isinstance(data_types, list) or not data_types or not all(isinstance(x, str) and x for x in data_types):
            raise SurvivorshipMetadataError(f"datasets.symbols[{index}].dataTypes must be a non-empty string list")
        since = _utc(item.get("availableSince"), field=f"datasets.symbols[{index}].availableSince")
        to = _utc(item.get("availableTo"), field=f"datasets.symbols[{index}].availableTo", nullable=True)
        assert since is not None
        if to is not None and to <= since:
            raise SurvivorshipMetadataError(f"datasets.symbols[{index}] has non-positive collection interval")

        records.append(
            {
                "symbol": symbol,
                "venue": VENUE,
                "provider_collection_available_since": _iso(since),
                "provider_collection_available_to": _iso(to),
                "provider_data_types": sorted(set(data_types)),
                "historical_membership_state": "UNRESOLVED",
                "delisting_state": "CENSORED_DELISTING_TIME_UNKNOWN" if to is not None else "UNRESOLVED",
                "current_active_field_consumed": False,
                "available_to_is_delisting_time": False,
                "enumeration_authority": "CANDIDATE_IDENTITY_ENUMERATION_ONLY",
            }
        )
    return sorted(records, key=lambda row: row["symbol"])


def build_survivorship_enumeration_manifest(
    provider_response_bytes: bytes,
    *,
    expected_source_response_sha256: str,
    captured_at: str,
) -> dict[str, Any]:
    """Build a deterministic no-label manifest from authenticated retained bytes.

    The result may be used only to ensure inactive/dead historical symbols receive
    identity-resolution work. It must never be consumed as proof that a symbol was a
    historical member at a decision time, that ``availableTo`` equals delisting time,
    or that an unresolved symbol is a matched non-winner. ``captured_at`` is retained
    for chronology/audit only and has no historical-availability authority without a
    separate trusted non-backdateable capture receipt.
    """

    provider_payload, digest = _authenticated_provider_payload(
        provider_response_bytes,
        expected_source_response_sha256=expected_source_response_sha256,
    )
    captured = _utc(captured_at, field="captured_at")
    assert captured is not None
    records = _symbol_records(provider_payload)

    semantic_fingerprint = _fingerprint(
        {
            "contract_id": CONTRACT_ID,
            "source_id": SOURCE_ID,
            "venue": VENUE,
            "symbols": records,
        }
    )
    core = {
        "schema_version": OUTPUT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "source_id": SOURCE_ID,
        "source_response_sha256": digest,
        "source_response_bytes_verified": True,
        "captured_at": _iso(captured),
        "capture_time_authority": "CALLER_DECLARED_NONE",
        "capture_time_is_historical_availability_proof": False,
        "venue": VENUE,
        "symbol_count": len(records),
        "symbols": records,
        "enumeration_semantic_fingerprint": semantic_fingerprint,
        "historical_membership_authority": "NONE",
        "delisting_time_authority": "NONE",
        "negative_control_authority": "NONE",
        "label_authority": "NONE",
        "candidate_authority": "NONE",
        "model_authority": "NONE",
        "broker_trading_authority": "NONE",
        "next_required_evidence": (
            "timestamp-safe exchange/provider identity and listing/delisting evidence before cohort membership or outcome use"
        ),
    }
    return {**core, "manifest_fingerprint": _fingerprint(core)}

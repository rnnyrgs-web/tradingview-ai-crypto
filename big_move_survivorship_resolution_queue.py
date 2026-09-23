"""Quarantine survivorship enumeration into a no-authority identity-resolution queue.

The Tardis exchange-details enumeration exists only to keep inactive/stopped symbols
from silently disappearing from later historical identity work.  It is *not* point-in-
time exchange membership evidence.  This module turns the enumeration manifest into a
structurally explicit unresolved work queue and exposes a fail-closed lineage guard for
the eventual Cohort-001 membership consumer.

Nothing emitted here can establish membership, tradability, delisting time, a matched
non-winner, a label, model evidence, a prospective candidate, or trading authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

ENUM_CONTRACT_ID = "2X-SURVIVORSHIP-METADATA-ENUMERATION-001-v1"
ENUM_SCHEMA = "2X-SURVIVORSHIP-ENUMERATION-MANIFEST-001-v1"
ENUM_AUTHORITY = "CANDIDATE_IDENTITY_ENUMERATION_ONLY"
QUEUE_CONTRACT_ID = "2X-SURVIVORSHIP-IDENTITY-RESOLUTION-QUEUE-001-v1"
QUEUE_SCHEMA = "2X-SURVIVORSHIP-IDENTITY-RESOLUTION-QUEUE-MANIFEST-001-v1"
WORK_ITEM_SCHEMA = "2X-SURVIVORSHIP-IDENTITY-RESOLUTION-WORK-ITEM-001-v1"
VENUE = "BINANCE_SPOT"
SOURCE_ID = "TARDIS_EXCHANGE_DETAILS_BINANCE"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_FORBIDDEN_MEMBERSHIP_LINEAGE_VALUES = {
    ENUM_AUTHORITY,
    ENUM_CONTRACT_ID,
    ENUM_SCHEMA,
    QUEUE_CONTRACT_ID,
    QUEUE_SCHEMA,
    WORK_ITEM_SCHEMA,
    "IDENTITY_RESOLUTION_WORK_QUEUE_ONLY",
    "UNRESOLVED_EXTERNAL_PIT_EVIDENCE_REQUIRED",
}
_FORBIDDEN_MEMBERSHIP_LINEAGE_KEYS = {
    "enumeration_manifest_fingerprint",
    "enumeration_semantic_fingerprint",
    "provider_collection_available_since",
    "provider_collection_available_to",
    "provider_collection_bounds_authority",
    "current_active_field_consumed",
    "available_to_is_delisting_time",
    "enumeration_authority",
    "work_item_fingerprint",
    "queue_fingerprint",
}


class SurvivorshipResolutionQueueError(ValueError):
    """Raised when no-authority enumeration data is malformed or misused."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise SurvivorshipResolutionQueueError(f"{field} must be lowercase SHA-256")
    return value


def _require_none_authority(value: Any, *, field: str) -> None:
    if value != "NONE":
        raise SurvivorshipResolutionQueueError(f"{field} must remain NONE")


def _validate_enumeration_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise SurvivorshipResolutionQueueError("enumeration manifest must be an object")
    if manifest.get("schema_version") != ENUM_SCHEMA:
        raise SurvivorshipResolutionQueueError("unexpected enumeration manifest schema")
    if manifest.get("contract_id") != ENUM_CONTRACT_ID:
        raise SurvivorshipResolutionQueueError("unexpected enumeration contract identity")
    if manifest.get("source_id") != SOURCE_ID or manifest.get("venue") != VENUE:
        raise SurvivorshipResolutionQueueError("enumeration source/venue identity mismatch")
    _sha256(manifest.get("source_response_sha256"), field="source_response_sha256")
    if manifest.get("source_response_bytes_verified") is not True:
        raise SurvivorshipResolutionQueueError("enumeration source bytes must already be verified")
    if manifest.get("capture_time_authority") != "CALLER_DECLARED_NONE":
        raise SurvivorshipResolutionQueueError("enumeration capture time must have zero authority")
    if manifest.get("capture_time_is_historical_availability_proof") is not False:
        raise SurvivorshipResolutionQueueError("capture time cannot become historical availability proof")
    for field in (
        "historical_membership_authority",
        "delisting_time_authority",
        "negative_control_authority",
        "label_authority",
        "candidate_authority",
        "model_authority",
        "broker_trading_authority",
    ):
        _require_none_authority(manifest.get(field), field=field)

    supplied_manifest_fingerprint = _sha256(
        manifest.get("manifest_fingerprint"), field="manifest_fingerprint"
    )
    core = dict(manifest)
    core.pop("manifest_fingerprint", None)
    if _fingerprint(core) != supplied_manifest_fingerprint:
        raise SurvivorshipResolutionQueueError("enumeration manifest fingerprint mismatch")

    symbols = manifest.get("symbols")
    if not isinstance(symbols, list):
        raise SurvivorshipResolutionQueueError("enumeration symbols must be a list")
    if manifest.get("symbol_count") != len(symbols):
        raise SurvivorshipResolutionQueueError("enumeration symbol_count mismatch")
    semantic = {
        "contract_id": ENUM_CONTRACT_ID,
        "source_id": SOURCE_ID,
        "venue": VENUE,
        "symbols": symbols,
    }
    if manifest.get("enumeration_semantic_fingerprint") != _fingerprint(semantic):
        raise SurvivorshipResolutionQueueError("enumeration semantic fingerprint mismatch")

    seen: set[str] = set()
    for index, item in enumerate(symbols):
        if not isinstance(item, dict):
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] must be an object")
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise SurvivorshipResolutionQueueError(f"symbols[{index}].symbol missing")
        if symbol in seen:
            raise SurvivorshipResolutionQueueError(
                f"duplicate/reused symbol {symbol} remains unresolved; it cannot be collapsed into one identity"
            )
        seen.add(symbol)
        if item.get("venue") != VENUE:
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] venue mismatch")
        if item.get("historical_membership_state") != "UNRESOLVED":
            raise SurvivorshipResolutionQueueError(
                f"symbols[{index}] cannot acquire historical membership in enumeration"
            )
        if item.get("enumeration_authority") != ENUM_AUTHORITY:
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] enumeration authority mismatch")
        if item.get("current_active_field_consumed") is not False:
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] current active state must be ignored")
        if item.get("available_to_is_delisting_time") is not False:
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] availableTo cannot be delisting time")
        data_types = item.get("provider_data_types")
        if not isinstance(data_types, list) or not all(isinstance(x, str) and x for x in data_types):
            raise SurvivorshipResolutionQueueError(f"symbols[{index}] provider_data_types malformed")
    return manifest


def build_identity_resolution_queue(enumeration_manifest: dict[str, Any]) -> dict[str, Any]:
    """Convert authenticated enumeration output into unresolved no-authority work items."""

    manifest = _validate_enumeration_manifest(enumeration_manifest)
    manifest_fingerprint = manifest["manifest_fingerprint"]
    source_response_sha256 = manifest["source_response_sha256"]
    items: list[dict[str, Any]] = []
    for row in manifest["symbols"]:
        core = {
            "schema_version": WORK_ITEM_SCHEMA,
            "venue": VENUE,
            "venue_symbol": row["symbol"],
            "enumeration_manifest_fingerprint": manifest_fingerprint,
            "source_response_sha256": source_response_sha256,
            "provider_collection_available_since": row.get("provider_collection_available_since"),
            "provider_collection_available_to": row.get("provider_collection_available_to"),
            "provider_data_types": list(row.get("provider_data_types", [])),
            "provider_collection_bounds_authority": "NONE",
            "identity_resolution_state": "UNRESOLVED_EXTERNAL_PIT_EVIDENCE_REQUIRED",
            "allowed_downstream_consumer": "IDENTITY_RESOLUTION_WORK_QUEUE_ONLY",
            "historical_membership_authority": "NONE",
            "delisting_time_authority": "NONE",
            "negative_control_authority": "NONE",
            "label_authority": "NONE",
            "cohort_snapshot_authority": False,
            "model_authority": "NONE",
            "prospective_candidate_authority": "NONE",
            "broker_trading_authority": "NONE",
        }
        items.append({**core, "work_item_fingerprint": _fingerprint(core)})

    items.sort(key=lambda item: item["venue_symbol"])
    core = {
        "schema_version": QUEUE_SCHEMA,
        "contract_id": QUEUE_CONTRACT_ID,
        "source_enumeration_contract_id": ENUM_CONTRACT_ID,
        "enumeration_manifest_fingerprint": manifest_fingerprint,
        "source_response_sha256": source_response_sha256,
        "venue": VENUE,
        "work_item_count": len(items),
        "work_items": items,
        "historical_membership_authority": "NONE",
        "delisting_time_authority": "NONE",
        "negative_control_authority": "NONE",
        "label_authority": "NONE",
        "cohort_snapshot_authority": False,
        "model_authority": "NONE",
        "prospective_candidate_authority": "NONE",
        "broker_trading_authority": "NONE",
        "next_required_evidence": (
            "separate timestamp-safe PIT identity interval and provider-native market-presence proof"
        ),
    }
    return {**core, "queue_fingerprint": _fingerprint(core)}


def reject_survivorship_enumeration_as_membership_lineage(value: Any) -> None:
    """Fail closed if enumeration/queue material is presented as membership lineage.

    This is the reusable boundary that the Cohort-001 membership consumer must invoke.
    Omission is not a bypass: a production membership provenance object must separately
    declare and authenticate provider-native PIT market-presence evidence.
    """

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key in _FORBIDDEN_MEMBERSHIP_LINEAGE_KEYS:
                    raise SurvivorshipResolutionQueueError(
                        f"survivorship enumeration/queue field forbidden in membership lineage: {path}.{key}"
                    )
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
        elif isinstance(node, str) and node in _FORBIDDEN_MEMBERSHIP_LINEAGE_VALUES:
            raise SurvivorshipResolutionQueueError(
                f"survivorship enumeration/queue authority forbidden in membership lineage: {path}"
            )

    walk(value, "$")


def validate_provider_native_membership_provenance(
    provenance: Any,
    *,
    venue_symbol: str,
    decision_at: str,
    source_proof_sha256: str,
) -> None:
    """Validate the non-enumeration envelope required by the membership boundary.

    This validates *lineage shape only*.  It does not itself authenticate provider
    bytes.  The existing source-authenticity layer must independently verify the exact
    `source_proof_sha256` and source-native proof before this envelope can be consumed.
    """

    reject_survivorship_enumeration_as_membership_lineage(provenance)
    if not isinstance(provenance, dict):
        raise SurvivorshipResolutionQueueError("membership provenance is required")
    expected_keys = {
        "schema",
        "source_kind",
        "venue",
        "venue_symbol",
        "decision_at",
        "source_proof_sha256",
        "enumeration_used_as_membership_evidence",
    }
    if set(provenance) != expected_keys:
        raise SurvivorshipResolutionQueueError("membership provenance fields must match frozen schema exactly")
    if provenance.get("schema") != "binance_market_presence_provenance.v1":
        raise SurvivorshipResolutionQueueError("unexpected membership provenance schema")
    if provenance.get("source_kind") != "BINANCE_PROVIDER_NATIVE_PIT_MARKET_PRESENCE":
        raise SurvivorshipResolutionQueueError("membership provenance must be provider-native PIT market presence")
    if provenance.get("venue") != VENUE or provenance.get("venue_symbol") != venue_symbol:
        raise SurvivorshipResolutionQueueError("membership provenance subject mismatch")
    if provenance.get("decision_at") != decision_at:
        raise SurvivorshipResolutionQueueError("membership provenance decision timestamp mismatch")
    if provenance.get("source_proof_sha256") != _sha256(source_proof_sha256, field="source_proof_sha256"):
        raise SurvivorshipResolutionQueueError("membership provenance source-proof binding mismatch")
    if provenance.get("enumeration_used_as_membership_evidence") is not False:
        raise SurvivorshipResolutionQueueError("survivorship enumeration cannot support membership")

from __future__ import annotations

import hashlib
import json
from typing import Any

SCIENTIFIC_DESIGN_FIELDS = (
    "target_markets",
    "target_timeframes",
    "data_contract",
    "signal_rules",
    "execution_rules",
    "cost_model",
    "validation_plan",
)

_UNORDERED_TOP_LEVEL_STRING_LISTS = {"target_markets", "target_timeframes"}
_UNORDERED_DATA_CONTRACT_STRING_LISTS = {"fixed_instruments"}


def _canonical_unordered_string_list(value: Any, field: str) -> list[str]:
    """Canonicalize schema-declared set-like lists without changing ordered rule sequences."""
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"{field} must be a non-empty list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError(f"{field} must contain non-empty strings")
        normalized.append(item.strip())
    if len(set(normalized)) != len(normalized):
        raise RuntimeError(f"{field} must not contain duplicates")
    return sorted(normalized)


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant behavior-driving projection for rejection memory.

    Dict key order is canonicalized during serialization. Fields that the
    predeclaration schema treats as unordered sets are normalized here too, so
    list permutations cannot create a cosmetic new scientific identity. Lists
    inside signal/execution rules remain ordered unless the schema explicitly
    declares them set-like.
    """
    if not isinstance(candidate, dict):
        raise RuntimeError("scientific design must be an object")
    missing = [field for field in SCIENTIFIC_DESIGN_FIELDS if field not in candidate]
    if missing:
        raise RuntimeError(f"scientific design missing fields: {missing}")

    projection = {field: candidate[field] for field in SCIENTIFIC_DESIGN_FIELDS}
    try:
        detached = json.loads(json.dumps(projection, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("scientific design must contain JSON-safe finite values") from exc

    for field in _UNORDERED_TOP_LEVEL_STRING_LISTS:
        detached[field] = _canonical_unordered_string_list(detached[field], field)

    data_contract = detached.get("data_contract")
    if isinstance(data_contract, dict):
        for field in _UNORDERED_DATA_CONTRACT_STRING_LISTS:
            if field in data_contract:
                data_contract[field] = _canonical_unordered_string_list(
                    data_contract[field], f"data_contract.{field}"
                )

    return detached


def canonical_scientific_design_bytes(candidate: dict[str, Any]) -> bytes:
    projection = scientific_design_projection(candidate)
    return json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def scientific_design_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_scientific_design_bytes(candidate)).hexdigest()

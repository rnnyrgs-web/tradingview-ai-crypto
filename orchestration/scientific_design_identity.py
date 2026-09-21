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


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant behavior-driving projection for rejection memory."""
    if not isinstance(candidate, dict):
        raise RuntimeError("scientific design must be an object")
    missing = [field for field in SCIENTIFIC_DESIGN_FIELDS if field not in candidate]
    if missing:
        raise RuntimeError(f"scientific design missing fields: {missing}")
    projection = {field: candidate[field] for field in SCIENTIFIC_DESIGN_FIELDS}
    try:
        return json.loads(json.dumps(projection, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("scientific design must contain JSON-safe finite values") from exc


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

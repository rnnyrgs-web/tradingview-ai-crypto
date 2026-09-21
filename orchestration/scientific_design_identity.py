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

SET_LIKE = "SET_LIKE"
ORDERED = "ORDERED"
SCIENTIFIC_LIST_SEMANTICS_VERSION = 1

# Every list reachable from SCIENTIFIC_DESIGN_FIELDS must be declared here.
# Unknown list paths fail closed instead of inheriting caller-order semantics.
# Use "*" for a list item when a supported ordered/set-like list contains
# structured children with additional declared list fields.
SCIENTIFIC_LIST_SEMANTICS: dict[tuple[str, ...], str] = {
    ("target_markets",): SET_LIKE,
    ("target_timeframes",): SET_LIKE,
    ("data_contract", "fixed_instruments"): SET_LIKE,
    ("data_contract", "fixed_follower_instruments"): SET_LIKE,
    ("data_contract", "symbols"): SET_LIKE,
    ("cost_model", "stress_multipliers"): SET_LIKE,
    ("validation_plan", "falsifier_compression_quantiles"): SET_LIKE,
    ("validation_plan", "falsifier_sigma_multiples"): SET_LIKE,
    ("validation_plan", "falsifier_underreaction_gap_values"): SET_LIKE,
    # Regression fixture and explicit example of a scientifically ordered list.
    ("signal_rules", "ordered_sequence"): ORDERED,
}


def _path_text(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "<root>"


def _list_semantics(path: tuple[str, ...]) -> str | None:
    direct = SCIENTIFIC_LIST_SEMANTICS.get(path)
    if direct is not None:
        return direct
    for pattern, semantics in SCIENTIFIC_LIST_SEMANTICS.items():
        if len(pattern) != len(path):
            continue
        if all(expected == actual or expected == "*" for expected, actual in zip(pattern, path)):
            return semantics
    return None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _canonicalize(value: Any, path: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize(child, path + (key,))
            for key, child in value.items()
        }

    if isinstance(value, list):
        semantics = _list_semantics(path)
        if semantics is None:
            raise RuntimeError(
                "scientific list semantics are undeclared for "
                f"{_path_text(path)} under version {SCIENTIFIC_LIST_SEMANTICS_VERSION}"
            )

        canonical_items: list[Any] = []
        for item in value:
            if semantics == SET_LIKE and isinstance(item, str):
                item = item.strip()
                if not item:
                    raise RuntimeError(
                        f"{_path_text(path)} SET_LIKE values must not contain empty strings"
                    )
            canonical_items.append(_canonicalize(item, path + ("*",)))

        if semantics == ORDERED:
            return canonical_items
        if semantics != SET_LIKE:
            raise RuntimeError(
                f"unsupported scientific list semantics {semantics!r} for {_path_text(path)}"
            )
        if not canonical_items:
            raise RuntimeError(f"{_path_text(path)} SET_LIKE list must not be empty")

        encoded = [(_canonical_json(item), item) for item in canonical_items]
        keys = [key for key, _ in encoded]
        if len(set(keys)) != len(keys):
            raise RuntimeError(f"{_path_text(path)} SET_LIKE list must not contain duplicates")
        encoded.sort(key=lambda pair: pair[0])
        return [item for _, item in encoded]

    return value


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant behavior-driving projection for rejection memory.

    Dict key order is canonicalized during serialization. Every behavior-driving
    list must have explicit versioned semantics: SET_LIKE lists are canonicalized
    deterministically, ORDERED lists preserve order, and unseen list paths fail
    closed. This prevents a rejected design from acquiring a fresh scientific
    identity merely by permuting a set-like list while preserving genuinely
    ordered signal/execution sequences.
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

    return _canonicalize(detached, ())


def canonical_scientific_design_bytes(candidate: dict[str, Any]) -> bytes:
    projection = scientific_design_projection(candidate)
    return _canonical_json(projection).encode("utf-8")


def scientific_design_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_scientific_design_bytes(candidate)).hexdigest()

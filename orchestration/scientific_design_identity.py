from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

from orchestration.strategy_behavior_schema import (
    BEHAVIOR_SCHEMA_REGISTRY_VERSION,
    BEHAVIOR_SCHEMAS,
    resolve_behavior_schema_id,
)

SCIENTIFIC_DESIGN_FIELDS = (
    "target_markets",
    "target_timeframes",
    "data_contract",
    "signal_rules",
    "execution_rules",
    "cost_model",
    "validation_plan",
)

# Rejected-memory needs a stricter behavior identity in addition to the full
# scientific protocol identity above. A failed executable design must not be
# resurrected merely by changing validation thresholds, baselines, fresh-window
# flags, or other evaluation-plan metadata while leaving the actual strategy
# behavior unchanged.
STRATEGY_BEHAVIOR_FIELDS = (
    "target_markets",
    "target_timeframes",
    "data_contract",
    "signal_rules",
    "execution_rules",
    "cost_model",
)

SET_LIKE = "SET_LIKE"
ORDERED = "ORDERED"
SCIENTIFIC_LIST_SEMANTICS_VERSION = 1
SCIENTIFIC_SCALAR_CANONICALIZATION_VERSION = 1
BEHAVIOR_FIELD_SEMANTICS_VERSION = 2
SCIENTIFIC_IDENTITY_VERSION = 2
STRATEGY_BEHAVIOR_IDENTITY_VERSION = 2

# Every list reachable from the identity fields must be declared here.
# Unknown list paths fail closed instead of inheriting caller-order semantics.
# Use "*" for a list item when a supported ordered/set-like list contains
# structured children with additional declared list fields.
SCIENTIFIC_LIST_SEMANTICS: dict[tuple[str, ...], str] = {
    ("target_markets",): SET_LIKE,
    ("target_timeframes",): SET_LIKE,
    ("data_contract", "fixed_instruments"): SET_LIKE,
    ("data_contract", "fixed_follower_instruments"): SET_LIKE,
    ("data_contract", "symbols"): SET_LIKE,
    ("data_contract", "spot_hedges"): SET_LIKE,
    ("data_contract", "required_freeze_before_screen"): SET_LIKE,
    ("cost_model", "stress_multipliers"): SET_LIKE,
    ("validation_plan", "falsifier_compression_quantiles"): SET_LIKE,
    ("validation_plan", "falsifier_sigma_multiples"): SET_LIKE,
    ("validation_plan", "falsifier_underreaction_gap_values"): SET_LIKE,
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


def _validate_behavior_field_semantics(candidate: dict[str, Any]) -> str:
    """Resolve one exact reviewed behavior schema and reject all other shapes.

    Recognition across schemas is used only to produce a useful error for truly
    unknown metadata. Admission itself is exact-shape and mechanism-specific:
    a field valid for another schema cannot be added to this strategy to create
    a new rejected-memory identity.
    """
    recognized: dict[str, set[str]] = {
        section: set().union(*(schema[section] for schema in BEHAVIOR_SCHEMAS.values()))
        for section in ("data_contract", "signal_rules", "execution_rules", "cost_model")
    }
    for section, allowed_anywhere in recognized.items():
        value = candidate.get(section)
        if not isinstance(value, dict):
            raise RuntimeError(f"{section} must be an object for behavior identity")
        undeclared = sorted(set(value) - allowed_anywhere)
        if undeclared:
            raise RuntimeError(
                f"undeclared behavior field(s) under semantics version "
                f"{BEHAVIOR_FIELD_SEMANTICS_VERSION}: "
                + ", ".join(f"{section}.{field}" for field in undeclared)
            )
        for field, child in value.items():
            if isinstance(child, dict):
                raise RuntimeError(
                    "nested behavior mappings require an explicit reviewed path schema: "
                    f"{section}.{field}"
                )
    return resolve_behavior_schema_id(candidate)


def _canonicalize_scalar(value: Any, path: tuple[str, ...]) -> Any:
    """Canonicalize JSON scalar representations for scientific identity only.

    JSON/Python numeric representations that execute equivalently must not create
    a fresh rejected-design identity. Booleans remain distinct from integers;
    integral finite floats collapse to their integer equivalent; negative zero
    collapses to zero; genuinely distinct non-integral values are not rounded.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError(f"{_path_text(path)} must contain finite numeric values")
        if value == 0.0:
            return 0
        if value.is_integer():
            return int(value)
        return value
    raise RuntimeError(
        f"unsupported scientific scalar type at {_path_text(path)}: {type(value).__name__}"
    )


def _canonicalize(value: Any, path: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(child, path + (key,)) for key, child in value.items()}

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

    return _canonicalize_scalar(value, path)


def _projection_for_fields(
    candidate: dict[str, Any],
    fields: Iterable[str],
    *,
    identity_name: str,
    bind_behavior_schema: bool = False,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise RuntimeError(f"{identity_name} must be an object")
    fields = tuple(fields)
    missing = [field for field in fields if field not in candidate]
    if missing:
        raise RuntimeError(f"{identity_name} missing fields: {missing}")

    behavior_schema_id = _validate_behavior_field_semantics(candidate)
    projection = {field: candidate[field] for field in fields}
    if bind_behavior_schema:
        projection = {
            "_behavior_schema": {
                "registry_version": BEHAVIOR_SCHEMA_REGISTRY_VERSION,
                "schema_id": behavior_schema_id,
            },
            **projection,
        }
    try:
        detached = json.loads(json.dumps(projection, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{identity_name} must contain JSON-safe finite values") from exc
    return _canonicalize(detached, ())


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant full scientific-protocol projection.

    This identity includes the validation plan. It answers whether two frozen
    experiments are the same complete scientific protocol. Behavior-container
    validity is still resolved through the exact schema registry, but the schema
    tag is not duplicated into this protocol digest.
    """
    return _projection_for_fields(
        candidate,
        SCIENTIFIC_DESIGN_FIELDS,
        identity_name="scientific design",
    )


def strategy_behavior_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label- and validation-plan-invariant executable projection.

    The resolved schema id and registry version are domain-bound into this
    identity. A candidate cannot switch to another mechanism's recognized field
    or caller-rename a schema without changing/failing the trusted resolver.
    """
    return _projection_for_fields(
        candidate,
        STRATEGY_BEHAVIOR_FIELDS,
        identity_name="strategy behavior",
        bind_behavior_schema=True,
    )


def canonical_scientific_design_bytes(candidate: dict[str, Any]) -> bytes:
    return _canonical_json(scientific_design_projection(candidate)).encode("utf-8")


def canonical_strategy_behavior_bytes(candidate: dict[str, Any]) -> bytes:
    return _canonical_json(strategy_behavior_projection(candidate)).encode("utf-8")


def scientific_design_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_scientific_design_bytes(candidate)).hexdigest()


def strategy_behavior_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_strategy_behavior_bytes(candidate)).hexdigest()

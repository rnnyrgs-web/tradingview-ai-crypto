from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

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
# scientific protocol identity above.  A failed executable design must not be
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
    # Cohort-001 delta-carry data contract: both are mathematical sets, not
    # executable sequences. Declaring them now keeps the first real cohort from
    # blocking after #507 integration while preserving fail-closed semantics.
    ("data_contract", "spot_hedges"): SET_LIKE,
    ("data_contract", "required_freeze_before_screen"): SET_LIKE,
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


def _projection_for_fields(
    candidate: dict[str, Any],
    fields: Iterable[str],
    *,
    identity_name: str,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise RuntimeError(f"{identity_name} must be an object")
    fields = tuple(fields)
    missing = [field for field in fields if field not in candidate]
    if missing:
        raise RuntimeError(f"{identity_name} missing fields: {missing}")

    projection = {field: candidate[field] for field in fields}
    try:
        detached = json.loads(json.dumps(projection, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{identity_name} must contain JSON-safe finite values") from exc
    return _canonicalize(detached, ())


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant full scientific-protocol projection.

    This identity includes the validation plan.  It answers whether two frozen
    experiments are the same complete scientific protocol.
    """
    return _projection_for_fields(
        candidate,
        SCIENTIFIC_DESIGN_FIELDS,
        identity_name="scientific design",
    )


def strategy_behavior_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label- and validation-plan-invariant executable projection.

    This identity is intentionally stricter for rejected-memory/no-rescue use:
    changing only an evaluation plan cannot resurrect a failed strategy whose
    markets, data, signal, execution and cost behavior are unchanged.
    """
    return _projection_for_fields(
        candidate,
        STRATEGY_BEHAVIOR_FIELDS,
        identity_name="strategy behavior",
    )


def canonical_scientific_design_bytes(candidate: dict[str, Any]) -> bytes:
    return _canonical_json(scientific_design_projection(candidate)).encode("utf-8")


def canonical_strategy_behavior_bytes(candidate: dict[str, Any]) -> bytes:
    return _canonical_json(strategy_behavior_projection(candidate)).encode("utf-8")


def scientific_design_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_scientific_design_bytes(candidate)).hexdigest()


def strategy_behavior_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_strategy_behavior_bytes(candidate)).hexdigest()

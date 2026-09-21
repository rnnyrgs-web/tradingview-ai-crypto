from __future__ import annotations

import hashlib
import json
import math
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
BEHAVIOR_FIELD_SEMANTICS_VERSION = 1
SCIENTIFIC_IDENTITY_VERSION = 2
STRATEGY_BEHAVIOR_IDENTITY_VERSION = 1

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

# A rejected executable strategy must not receive a fresh behavior identity by
# adding caller-authored metadata inside a behavior container. Every admitted
# field below is explicitly treated as behavior-driving by this versioned
# contract. Unknown keys fail closed before either scientific or behavior
# hashing. Nested mappings are also rejected until their own path semantics are
# explicitly versioned here; current supported contracts are intentionally flat
# inside these four behavior containers.
BEHAVIOR_DRIVING_FIELDS: dict[str, frozenset[str]] = {
    "data_contract": frozenset(
        {
            "source",
            "point_in_time",
            "historical_universe",
            "venue",
            "instrument_type",
            "bar_interval",
            "completed_bars_only",
            "fixed_instruments",
            "asset_substitution_allowed",
            "leader_instrument",
            "fixed_follower_instruments",
            "normalized_rows_sha256",
            "bar",
            "normalized_row_count",
            "coverage_start_utc",
            "coverage_end_utc",
            "selection_train_start_utc",
            "selection_train_end_utc",
            "selection_validation_start_utc",
            "selection_validation_end_utc",
            "protected_oos_start_utc",
            "protected_oos_end_utc",
            "screen_may_read_protected_oos",
            "spot_hedges",
            "required_freeze_before_screen",
            "symbols",
        }
    ),
    "signal_rules": frozenset(
        {
            "shock_definition",
            "entry_condition",
            "threshold",
            "ordered_sequence",
            "compression_metric",
            "compression_reference_window_bars",
            "compression_quantile",
            "compression_recency_bars",
            "breakout_window_bars",
            "atr_window_bars",
            "long_rule",
            "short_rule",
            "return_definition",
            "volatility_window_bars",
            "volatility_estimator",
            "absolute_return_floor",
            "sigma_multiple",
            "quote_volume_window_bars",
            "quote_volume_ratio_min",
            "range_window_bars",
            "range_ratio_min",
            "normalized_range",
            "direction",
            "trailing_window_bars",
            "leader_impulse_absolute_return_floor",
            "leader_impulse_sigma_multiple",
            "follower_beta_type",
            "follower_beta_window_bars",
            "follower_beta_min",
            "follower_beta_max",
            "underreaction_gap_min",
            "opposite_move_guard",
            "lookback_hours",
            "per_asset_return",
            "direction_gate",
            "strength_gate",
            "dispersion_gate",
            "decision_time",
            "warmup_hours",
            "beta_estimation_hours",
            "beta_input",
            "residual_horizon_hours",
            "residual",
            "zscore_window_hours",
            "entry_gate",
            "signed_volume_per_bar",
            "aggregation_hours",
            "direction_consistency",
            "pressure_gate",
            "close_location_gate",
            "range_guard",
            "move_horizon_hours",
            "move_gate",
            "participation_gate",
            "shock_exclusion",
            "measurement_window",
            "signal_clock",
            "minimum_history_days",
            "realized_vol_window_hours",
            "vol_reference_window_hours",
            "vol_regime",
            "participation_guard",
            "range_lookback_hours",
            "efficiency_ratio",
            "regime_gate",
            "range_position",
            "volume_guard",
            "atr_window_hours",
            "funding_history",
            "carry_gate",
            "basis_guard",
            "future_funding_rate_usage",
        }
    ),
    "execution_rules": frozenset(
        {
            "entry_delay_bars",
            "exit_rule",
            "position_overlap",
            "decision_timestamp",
            "entry_price",
            "stop_atr_multiple",
            "target_atr_multiple",
            "maximum_hold_bars",
            "one_position_per_instrument",
            "same_bar_stop_target_collision",
            "stop_gap_policy",
            "target_gap_policy",
            "holding_period_bars",
            "exit_price",
            "stop",
            "target",
            "one_position_per_follower",
            "cross_follower_positions_allowed",
            "per_position_nav_fraction",
            "max_concurrent_positions",
            "max_gross_exposure_nav_fraction",
            "entry",
            "direction",
            "portfolio",
            "hold_hours",
            "overlap",
            "exit",
            "gross_notional",
            "take_profit",
            "max_hold_hours",
            "legs",
            "hold",
            "borrow_assumption",
        }
    ),
    "cost_model": frozenset(
        {
            "fees_bps",
            "spread_bps",
            "slippage_bps",
            "funding_bps_per_day",
            "stress_multipliers",
            "base_round_trip_bps",
            "selection_uses_max_stress",
            "funding_carry_bps",
        }
    ),
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


def _validate_behavior_field_semantics(candidate: dict[str, Any]) -> None:
    """Reject caller-defined behavior metadata before identity hashing.

    The admitted behavior schema is deliberately explicit. A new executable
    field requires a reviewed update to this versioned registry instead of being
    silently accepted as identity-changing caller metadata.
    """
    for section, allowed_fields in BEHAVIOR_DRIVING_FIELDS.items():
        value = candidate.get(section)
        if not isinstance(value, dict):
            raise RuntimeError(f"{section} must be an object for behavior identity")
        undeclared = sorted(set(value) - set(allowed_fields))
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

    return _canonicalize_scalar(value, path)


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

    _validate_behavior_field_semantics(candidate)
    projection = {field: candidate[field] for field in fields}
    try:
        detached = json.loads(json.dumps(projection, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{identity_name} must contain JSON-safe finite values") from exc
    return _canonicalize(detached, ())


def scientific_design_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the label-invariant full scientific-protocol projection.

    This identity includes the validation plan. It answers whether two frozen
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

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

BEHAVIOR_SCHEMA_REGISTRY_VERSION = 1
BEHAVIOR_SECTIONS = ("data_contract", "signal_rules", "execution_rules", "cost_model")


def _fields(*names: str) -> frozenset[str]:
    return frozenset(names)


def _schema(
    *,
    data_contract: frozenset[str],
    signal_rules: frozenset[str],
    execution_rules: frozenset[str],
    cost_model: frozenset[str],
) -> dict[str, frozenset[str]]:
    return {
        "data_contract": data_contract,
        "signal_rules": signal_rules,
        "execution_rules": execution_rules,
        "cost_model": cost_model,
    }


COMMON_PREDECLARATION_COST = _fields(
    "fees_bps",
    "spread_bps",
    "slippage_bps",
    "funding_bps_per_day",
    "stress_multipliers",
)

COMMON_COHORT_OHLCV_COST = _fields(
    "fees_bps",
    "spread_bps",
    "slippage_bps",
    "adverse_funding_allowance_bps_per_trade",
    "stress_multipliers",
)

COMMON_COHORT_OHLCV_DATA = _fields(
    "source",
    "bar",
    "fixed_instruments",
    "normalized_rows_sha256",
    "normalized_row_count",
    "coverage_start_utc",
    "coverage_end_utc",
    "selection_train_start_utc",
    "selection_train_end_utc",
    "selection_validation_start_utc",
    "selection_validation_end_utc",
    "protected_oos_start_utc",
    "protected_oos_end_utc",
    "point_in_time",
    "screen_may_read_protected_oos",
    "historical_universe",
)

# This is intentionally an exact-shape registry, not a global union allow-list.
# A field valid for one strategy schema is not automatically valid for another.
# New executable shapes require a reviewed registry change. Schema selection is
# derived from the exact four behavior-container key sets; callers do not choose
# an arbitrary schema id.
BEHAVIOR_SCHEMAS: dict[str, dict[str, frozenset[str]]] = {
    # Reconstructible canonical rejected designs.
    "DISC_VOL_BREAKOUT_V1": _schema(
        data_contract=_fields(
            "venue",
            "instrument_type",
            "bar_interval",
            "completed_bars_only",
            "fixed_instruments",
            "asset_substitution_allowed",
        ),
        signal_rules=_fields(
            "compression_metric",
            "compression_reference_window_bars",
            "compression_quantile",
            "compression_recency_bars",
            "breakout_window_bars",
            "atr_window_bars",
            "long_rule",
            "short_rule",
        ),
        execution_rules=_fields(
            "decision_timestamp",
            "entry_delay_bars",
            "entry_price",
            "stop_atr_multiple",
            "target_atr_multiple",
            "maximum_hold_bars",
            "one_position_per_instrument",
            "same_bar_stop_target_collision",
            "stop_gap_policy",
            "target_gap_policy",
        ),
        cost_model=_fields(
            "base_round_trip_bps",
            "stress_multipliers",
            "selection_uses_max_stress",
        ),
    ),
    "DISC_LIQUIDITY_MEANREV_V1": _schema(
        data_contract=_fields(
            "venue",
            "instrument_type",
            "bar_interval",
            "completed_bars_only",
            "fixed_instruments",
            "asset_substitution_allowed",
        ),
        signal_rules=_fields(
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
        ),
        execution_rules=_fields(
            "decision_timestamp",
            "entry_delay_bars",
            "entry_price",
            "holding_period_bars",
            "exit_price",
            "stop",
            "target",
            "one_position_per_instrument",
        ),
        cost_model=_fields(
            "base_round_trip_bps",
            "stress_multipliers",
            "selection_uses_max_stress",
        ),
    ),
    "DISC_BTC_LEADLAG_V1": _schema(
        data_contract=_fields(
            "venue",
            "instrument_type",
            "bar_interval",
            "completed_bars_only",
            "leader_instrument",
            "fixed_follower_instruments",
            "asset_substitution_allowed",
            "normalized_rows_sha256",
        ),
        signal_rules=_fields(
            "return_definition",
            "trailing_window_bars",
            "leader_impulse_absolute_return_floor",
            "leader_impulse_sigma_multiple",
            "follower_beta_type",
            "follower_beta_window_bars",
            "follower_beta_min",
            "follower_beta_max",
            "underreaction_gap_min",
            "opposite_move_guard",
            "direction",
        ),
        execution_rules=_fields(
            "decision_timestamp",
            "entry_delay_bars",
            "entry_price",
            "holding_period_bars",
            "exit_price",
            "one_position_per_follower",
            "cross_follower_positions_allowed",
            "per_position_nav_fraction",
            "max_concurrent_positions",
            "max_gross_exposure_nav_fraction",
        ),
        cost_model=_fields(
            "base_round_trip_bps",
            "fees_bps",
            "spread_bps",
            "slippage_bps",
            "funding_carry_bps",
            "stress_multipliers",
            "selection_uses_max_stress",
        ),
    ),
    # Strategy Factory Cohort 001 frozen seed shapes. Registration grants only
    # identity/admission semantics; it grants no screening or outcome authority.
    "C101_BREADTH_PERSIST_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "lookback_hours",
            "per_asset_return",
            "direction_gate",
            "strength_gate",
            "dispersion_gate",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields(
            "entry",
            "direction",
            "portfolio",
            "hold_hours",
            "overlap",
            "stop",
        ),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_RESIDUAL_REV_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "beta_estimation_hours",
            "beta_input",
            "residual_horizon_hours",
            "residual",
            "zscore_window_hours",
            "entry_gate",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields(
            "entry",
            "direction",
            "hold_hours",
            "exit",
            "overlap",
            "gross_notional",
        ),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_SIGNED_VOLUME_DRIFT_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "signed_volume_per_bar",
            "aggregation_hours",
            "direction_consistency",
            "pressure_gate",
            "close_location_gate",
            "range_guard",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields("entry", "direction", "hold_hours", "exit", "overlap"),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_LOWVOL_DRIFT_REV_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "move_horizon_hours",
            "move_gate",
            "participation_gate",
            "shock_exclusion",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields("entry", "direction", "hold_hours", "exit", "overlap"),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_WEEKEND_NORMALIZE_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "measurement_window",
            "signal_clock",
            "move_gate",
            "participation_gate",
            "minimum_history_days",
            "decision_time",
        ),
        execution_rules=_fields("entry", "direction", "hold_hours", "exit", "overlap"),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_MODERATEVOL_AUTOCORR_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "direction_gate",
            "realized_vol_window_hours",
            "vol_reference_window_hours",
            "vol_regime",
            "participation_guard",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields("entry", "direction", "hold_hours", "exit", "overlap"),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_RANGE_AUCTION_REV_V1": _schema(
        data_contract=COMMON_COHORT_OHLCV_DATA,
        signal_rules=_fields(
            "range_lookback_hours",
            "efficiency_ratio",
            "regime_gate",
            "range_position",
            "entry_gate",
            "volume_guard",
            "atr_window_hours",
            "decision_time",
            "warmup_hours",
        ),
        execution_rules=_fields(
            "entry",
            "direction",
            "take_profit",
            "stop",
            "max_hold_hours",
            "overlap",
        ),
        cost_model=COMMON_COHORT_OHLCV_COST,
    ),
    "C101_DELTA_CARRY_V1": _schema(
        data_contract=_fields(
            "source",
            "bar",
            "fixed_instruments",
            "spot_hedges",
            "point_in_time",
            "historical_universe",
            "required_freeze_before_screen",
            "screen_may_read_protected_oos",
        ),
        signal_rules=_fields(
            "funding_history",
            "direction_gate",
            "carry_gate",
            "basis_guard",
            "decision_time",
            "future_funding_rate_usage",
        ),
        execution_rules=_fields(
            "entry",
            "legs",
            "hold",
            "exit",
            "overlap",
            "borrow_assumption",
        ),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    # Exact-shape regression fixtures. These are retained in the complete
    # registry for value-contract coverage, but production resolution excludes
    # them by construction. Tests may opt in only through the process-local
    # context manager below; no candidate field can enable them.
    "TEST_SYNTHETIC_LIQUIDITY_V1": _schema(
        data_contract=_fields("source", "point_in_time", "historical_universe"),
        signal_rules=_fields("shock_definition", "entry_condition"),
        execution_rules=_fields("entry_delay_bars", "exit_rule", "position_overlap"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    "TEST_BEHAVIOR_IDENTITY_V1": _schema(
        data_contract=_fields("source", "point_in_time"),
        signal_rules=_fields("threshold", "entry_condition"),
        execution_rules=_fields("entry_delay_bars", "exit_rule"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    "TEST_FIELD_SEMANTICS_V1": _schema(
        data_contract=_fields("source", "point_in_time", "historical_universe"),
        signal_rules=_fields("threshold", "entry_condition"),
        execution_rules=_fields("entry_delay_bars", "exit_rule"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    "TEST_IDENTITY_PERMUTATION_V1": _schema(
        data_contract=_fields(
            "source", "point_in_time", "historical_universe", "fixed_instruments"
        ),
        signal_rules=_fields("entry_condition", "ordered_sequence"),
        execution_rules=_fields("entry_delay_bars", "exit_rule"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    "TEST_IDENTITY_PERMUTATION_SYMBOLS_V1": _schema(
        data_contract=_fields(
            "source",
            "point_in_time",
            "historical_universe",
            "fixed_instruments",
            "symbols",
        ),
        signal_rules=_fields("entry_condition", "ordered_sequence"),
        execution_rules=_fields("entry_delay_bars", "exit_rule"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
    "TEST_IDENTITY_PERMUTATION_CARRYSETS_V1": _schema(
        data_contract=_fields(
            "source",
            "point_in_time",
            "historical_universe",
            "fixed_instruments",
            "spot_hedges",
            "required_freeze_before_screen",
        ),
        signal_rules=_fields("entry_condition", "ordered_sequence"),
        execution_rules=_fields("entry_delay_bars", "exit_rule"),
        cost_model=COMMON_PREDECLARATION_COST,
    ),
}

PRODUCTION_BEHAVIOR_SCHEMAS: dict[str, dict[str, frozenset[str]]] = {
    schema_id: schema
    for schema_id, schema in BEHAVIOR_SCHEMAS.items()
    if not schema_id.startswith("TEST_")
}
TEST_BEHAVIOR_SCHEMAS: dict[str, dict[str, frozenset[str]]] = {
    schema_id: schema
    for schema_id, schema in BEHAVIOR_SCHEMAS.items()
    if schema_id.startswith("TEST_")
}
if not PRODUCTION_BEHAVIOR_SCHEMAS or not TEST_BEHAVIOR_SCHEMAS:
    raise RuntimeError("behavior schema registry must contain production and test-only partitions")

_ALLOW_TEST_SCHEMAS: ContextVar[bool] = ContextVar(
    "strategy_behavior_allow_test_schemas",
    default=False,
)


@contextmanager
def allow_test_behavior_schemas() -> Iterator[None]:
    """Explicit process-local injection for regression fixtures only.

    Production resolution defaults to the reviewed production partition. A
    candidate cannot select this context through its payload, labels, schema id,
    or any other predeclaration field.
    """
    token = _ALLOW_TEST_SCHEMAS.set(True)
    try:
        yield
    finally:
        _ALLOW_TEST_SCHEMAS.reset(token)


def behavior_shape(candidate: dict[str, Any]) -> dict[str, frozenset[str]]:
    if not isinstance(candidate, dict):
        raise RuntimeError("strategy behavior must be an object")
    observed: dict[str, frozenset[str]] = {}
    for section in BEHAVIOR_SECTIONS:
        value = candidate.get(section)
        if not isinstance(value, dict):
            raise RuntimeError(f"{section} must be an object for behavior identity")
        observed[section] = frozenset(value)
    return observed


def resolve_behavior_schema_id(candidate: dict[str, Any]) -> str:
    observed = behavior_shape(candidate)
    registry = BEHAVIOR_SCHEMAS if _ALLOW_TEST_SCHEMAS.get() else PRODUCTION_BEHAVIOR_SCHEMAS
    matches = [
        schema_id
        for schema_id, schema in registry.items()
        if all(observed[section] == schema[section] for section in BEHAVIOR_SECTIONS)
    ]
    if not matches:
        details = "; ".join(
            f"{section}={','.join(sorted(observed[section]))}" for section in BEHAVIOR_SECTIONS
        )
        raise RuntimeError(
            "unsupported behavior schema shape under registry version "
            f"{BEHAVIOR_SCHEMA_REGISTRY_VERSION}: {details}"
        )
    if len(matches) != 1:
        raise RuntimeError(
            "ambiguous behavior schema shape under registry version "
            f"{BEHAVIOR_SCHEMA_REGISTRY_VERSION}: {sorted(matches)}"
        )
    return matches[0]

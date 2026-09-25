from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from orchestration.strategy_behavior_schema import BEHAVIOR_SCHEMAS, BEHAVIOR_SECTIONS

BEHAVIOR_VALUE_CONTRACT_VERSION = 1

_NUMBER = "NUMBER"
_BOOL = "BOOL"
_NULL = "NULL"
_CLOSED_LITERAL = "TOKEN"
_INSTRUMENT = "INSTRUMENT"
_SHA256 = "SHA256"
_UTC_TIMESTAMP = "UTC_TIMESTAMP"
_NUMBER_LIST = "NUMBER_LIST"
_INSTRUMENT_SET = "INSTRUMENT_SET"
_SYMBOL_SET = "SYMBOL_SET"
_CLOSED_LITERAL_SET = "TOKEN_SET"
_ORDERED_LITERAL_LIST = "ORDERED_TOKEN_LIST"

_INSTRUMENT_RE = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)+$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMEFRAME_RE = re.compile(r"^[1-9][0-9]*[mhdw]$")


@dataclass(frozen=True)
class ValueRule:
    kind: str
    tokens: frozenset[str] = frozenset()


def number() -> ValueRule:
    return ValueRule(_NUMBER)


def boolean() -> ValueRule:
    return ValueRule(_BOOL)


def null() -> ValueRule:
    return ValueRule(_NULL)


def token(*values: str) -> ValueRule:
    if not values:
        raise RuntimeError("closed token rule requires at least one value")
    return ValueRule(_CLOSED_LITERAL, frozenset(values))


def instrument() -> ValueRule:
    return ValueRule(_INSTRUMENT)


def sha256() -> ValueRule:
    return ValueRule(_SHA256)


def utc_timestamp() -> ValueRule:
    return ValueRule(_UTC_TIMESTAMP)


def number_list() -> ValueRule:
    return ValueRule(_NUMBER_LIST)


def instrument_set() -> ValueRule:
    return ValueRule(_INSTRUMENT_SET)


def symbol_set() -> ValueRule:
    return ValueRule(_SYMBOL_SET)


def token_set(*values: str) -> ValueRule:
    if not values:
        raise RuntimeError("closed token-set rule requires at least one value")
    return ValueRule(_CLOSED_LITERAL_SET, frozenset(values))


def ordered_tokens(*values: str) -> ValueRule:
    if not values:
        raise RuntimeError("ordered token-list rule requires at least one value")
    return ValueRule(_ORDERED_LITERAL_LIST, frozenset(values))


def _section(**rules: ValueRule) -> dict[str, ValueRule]:
    return rules


COMMON_COST = _section(
    fees_bps=number(),
    spread_bps=number(),
    slippage_bps=number(),
    funding_bps_per_day=number(),
    stress_multipliers=number_list(),
)

COMMON_COHORT_OHLCV_COST = _section(
    fees_bps=number(),
    spread_bps=number(),
    slippage_bps=number(),
    adverse_funding_allowance_bps_per_trade=number(),
    stress_multipliers=number_list(),
)

COMMON_COHORT_DATA = _section(
    source=token("OKX /api/v5/market/history-candles"),
    bar=token("1H"),
    fixed_instruments=instrument_set(),
    normalized_rows_sha256=sha256(),
    normalized_row_count=number(),
    coverage_start_utc=utc_timestamp(),
    coverage_end_utc=utc_timestamp(),
    selection_train_start_utc=utc_timestamp(),
    selection_train_end_utc=utc_timestamp(),
    selection_validation_start_utc=utc_timestamp(),
    selection_validation_end_utc=utc_timestamp(),
    protected_oos_start_utc=utc_timestamp(),
    protected_oos_end_utc=utc_timestamp(),
    point_in_time=boolean(),
    screen_may_read_protected_oos=boolean(),
    historical_universe=token("fixed_predeclared_assets"),
)

REJECT_COMMON_DATA = _section(
    venue=token("OKX"),
    instrument_type=token("USDT-margined perpetual swap"),
    bar_interval=token("1H"),
    completed_bars_only=boolean(),
    fixed_instruments=instrument_set(),
    asset_substitution_allowed=boolean(),
)

REJECT_COMMON_COST = _section(
    base_round_trip_bps=number(),
    stress_multipliers=number_list(),
    selection_uses_max_stress=boolean(),
)

TEST_COST = COMMON_COST

# Every accepted production string below is a CLOSED REVIEWED TOKEN. Some legacy
# tokens are sentence-shaped because they were frozen before this contract; they
# are not free prose. Paraphrases fail closed. A future new token or value shape
# requires a reviewed registry change and a version bump when semantics change.
BEHAVIOR_VALUE_CONTRACTS: dict[str, dict[str, dict[str, ValueRule]]] = {
    "DISC_VOL_BREAKOUT_V1": {
        "data_contract": REJECT_COMMON_DATA,
        "signal_rules": _section(
            compression_metric=token("ATR(14)/close"),
            compression_reference_window_bars=number(),
            compression_quantile=number(),
            compression_recency_bars=number(),
            breakout_window_bars=number(),
            atr_window_bars=number(),
            long_rule=token("close strictly above prior 20-bar high with recent compression"),
            short_rule=token("close strictly below prior 20-bar low with recent compression"),
        ),
        "execution_rules": _section(
            decision_timestamp=token("completed signal-bar close"),
            entry_delay_bars=number(),
            entry_price=token("next bar open"),
            stop_atr_multiple=number(),
            target_atr_multiple=number(),
            maximum_hold_bars=number(),
            one_position_per_instrument=boolean(),
            same_bar_stop_target_collision=token("stop_first_pessimistic"),
            stop_gap_policy=token("fill at observed bar open if worse"),
            target_gap_policy=token("cap fill at target"),
        ),
        "cost_model": REJECT_COMMON_COST,
    },
    "DISC_LIQUIDITY_MEANREV_V1": {
        "data_contract": REJECT_COMMON_DATA,
        "signal_rules": _section(
            return_definition=token("close[t]/close[t-1]-1"),
            volatility_window_bars=number(),
            volatility_estimator=token("sample_std_prior_completed_returns_excluding_signal"),
            absolute_return_floor=number(),
            sigma_multiple=number(),
            quote_volume_window_bars=number(),
            quote_volume_ratio_min=number(),
            range_window_bars=number(),
            range_ratio_min=number(),
            normalized_range=token("(high-low)/previous_close"),
            direction=token("opposite signal return"),
        ),
        "execution_rules": _section(
            decision_timestamp=token("completed signal-bar close"),
            entry_delay_bars=number(),
            entry_price=token("next bar open"),
            holding_period_bars=number(),
            exit_price=token("open after six full post-entry bars"),
            stop=null(),
            target=null(),
            one_position_per_instrument=boolean(),
        ),
        "cost_model": REJECT_COMMON_COST,
    },
    "DISC_BTC_LEADLAG_V1": {
        "data_contract": _section(
            venue=token("OKX"),
            instrument_type=token("USDT-margined perpetual swap"),
            bar_interval=token("1H"),
            completed_bars_only=boolean(),
            leader_instrument=instrument(),
            fixed_follower_instruments=instrument_set(),
            asset_substitution_allowed=boolean(),
            normalized_rows_sha256=sha256(),
        ),
        "signal_rules": _section(
            return_definition=token("aligned hourly close[t]/close[t-1]-1"),
            trailing_window_bars=number(),
            leader_impulse_absolute_return_floor=number(),
            leader_impulse_sigma_multiple=number(),
            follower_beta_type=token("OLS_THROUGH_ORIGIN"),
            follower_beta_window_bars=number(),
            follower_beta_min=number(),
            follower_beta_max=number(),
            underreaction_gap_min=number(),
            opposite_move_guard=number(),
            direction=token("same as qualifying BTC impulse"),
        ),
        "execution_rules": _section(
            decision_timestamp=token("aligned completed signal-bar close"),
            entry_delay_bars=number(),
            entry_price=token("follower next bar open"),
            holding_period_bars=number(),
            exit_price=token("follower open after six full post-entry bars"),
            one_position_per_follower=boolean(),
            cross_follower_positions_allowed=boolean(),
            per_position_nav_fraction=number(),
            max_concurrent_positions=number(),
            max_gross_exposure_nav_fraction=number(),
        ),
        "cost_model": _section(
            base_round_trip_bps=number(),
            fees_bps=number(),
            spread_bps=number(),
            slippage_bps=number(),
            funding_carry_bps=number(),
            stress_multipliers=number_list(),
            selection_uses_max_stress=boolean(),
        ),
    },
    "C101_BREADTH_PERSIST_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            lookback_hours=number(),
            per_asset_return=token("close_t / close_t_minus_6h - 1"),
            direction_gate=token("all three 6h returns have the same non-zero sign"),
            strength_gate=token("median(abs(6h return across assets)) >= rolling_30d_median_of_same_statistic"),
            dispersion_gate=token("cross_sectional_std(6h returns) <= rolling_30d_60th_percentile_of_same_statistic"),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open after signal"),
            direction=token("same as synchronized basket sign"),
            portfolio=token("equal notional BTC/ETH/SOL basket"),
            hold_hours=number(),
            overlap=token("ignore new signals while basket position is open"),
            stop=token("none in cheap screen; fixed-hold falsification only"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_RESIDUAL_REV_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            beta_estimation_hours=number(),
            beta_input=token("hourly close-to-close returns ending at t"),
            residual_horizon_hours=number(),
            residual=token("follower_6h_return - rolling_beta * btc_6h_return"),
            zscore_window_hours=number(),
            entry_gate=token("abs(residual_zscore) >= 2.0 and rolling follower/BTC return correlation >= 0.60"),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open"),
            direction=token("opposite residual sign in follower; BTC hedge sized by frozen rolling beta"),
            hold_hours=number(),
            exit=token("fixed 6h hold"),
            overlap=token("one open pair per follower; same-follower signals ignored until flat"),
            gross_notional=token("1.0 follower leg plus abs(beta) BTC hedge leg"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_SIGNED_VOLUME_DRIFT_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            signed_volume_per_bar=token("sign(close-open) * quote_volume / rolling_30d_median_quote_volume"),
            aggregation_hours=number(),
            direction_consistency=token("at least 3 of last 4 completed bars share aggregate sign"),
            pressure_gate=token("abs(sum(last_4_signed_volume)) >= rolling_30d_90th_percentile_abs_sum"),
            close_location_gate=token("long if close_location_in_bar >= 0.80; short if <= 0.20"),
            range_guard=token("current true range <= rolling_30d_90th_percentile_true_range"),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open"),
            direction=token("same as aggregate signed-volume sign"),
            hold_hours=number(),
            exit=token("fixed 3h hold"),
            overlap=token("one position per asset; ignore overlapping same-asset signals"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_LOWVOL_DRIFT_REV_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            move_horizon_hours=number(),
            move_gate=token("abs(8h return) >= rolling_30d_80th_percentile_abs_8h_return"),
            participation_gate=token("mean_quote_volume_last_8h <= 0.60 * rolling_30d_median_hourly_quote_volume"),
            shock_exclusion=token("max_true_range_last_8h < rolling_30d_70th_percentile_hourly_true_range"),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open"),
            direction=token("opposite sign of 8h return"),
            hold_hours=number(),
            exit=token("fixed 6h hold"),
            overlap=token("one position per asset; ignore overlapping same-asset signals"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_WEEKEND_NORMALIZE_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            measurement_window=token("Friday 22:00 UTC close to Sunday 23:00 UTC close"),
            signal_clock=token("Sunday 23:00 UTC completed bar"),
            move_gate=token("abs(weekend_return) >= 1.25%"),
            participation_gate=token("median_weekend_hourly_quote_volume <= 0.80 * median_hourly_quote_volume_of_prior_20_weekdays"),
            minimum_history_days=number(),
            decision_time=token("Sunday 23:00 UTC completed bar only"),
        ),
        "execution_rules": _section(
            entry=token("Monday 00:00 UTC bar open"),
            direction=token("opposite weekend return sign"),
            hold_hours=number(),
            exit=token("fixed 12h hold"),
            overlap=token("maximum one position per asset per calendar week"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_MODERATEVOL_AUTOCORR_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            direction_gate=token("last 3 completed hourly close-to-close returns all strictly positive or all strictly negative"),
            realized_vol_window_hours=number(),
            vol_reference_window_hours=number(),
            vol_regime=token("24h realized volatility between trailing 90d 35th and 70th percentiles"),
            participation_guard=token("current quote_volume between trailing_30d 40th and 90th percentiles"),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open"),
            direction=token("same as last 3 hourly returns"),
            hold_hours=number(),
            exit=token("fixed 3h hold"),
            overlap=token("one position per asset; ignore overlapping same-asset signals"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_RANGE_AUCTION_REV_V1": {
        "data_contract": COMMON_COHORT_DATA,
        "signal_rules": _section(
            range_lookback_hours=number(),
            efficiency_ratio=token("abs(close_t-close_t_minus_24h) / sum(abs(hourly_close_change), last_24h)"),
            regime_gate=token("efficiency_ratio <= 0.25"),
            range_position=token("(close_t-prior_48h_low)/(prior_48h_high-prior_48h_low), prior range excludes current bar"),
            entry_gate=token("short if range_position >= 0.90; long if <= 0.10"),
            volume_guard=token("current quote_volume <= trailing_30d_60th_percentile"),
            atr_window_hours=number(),
            decision_time=token("completed 1h bar close only"),
            warmup_hours=number(),
        ),
        "execution_rules": _section(
            entry=token("next completed bar open"),
            direction=token("toward prior 48h range midpoint"),
            take_profit=token("exit at next bar open after a completed bar close crosses the frozen prior-range midpoint"),
            stop=token("exit at next bar open after a completed bar high/low breaches entry by 1.0 * ATR14 against position"),
            max_hold_hours=number(),
            overlap=token("one position per asset; ignore overlapping same-asset signals"),
        ),
        "cost_model": COMMON_COHORT_OHLCV_COST,
    },
    "C101_DELTA_CARRY_V1": {
        "data_contract": _section(
            source=token("Public OKX/Binance funding history plus OKX completed spot/perpetual candles; no paid provider"),
            bar=token("1H plus realized funding timestamps"),
            fixed_instruments=instrument_set(),
            spot_hedges=instrument_set(),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
            required_freeze_before_screen=token_set(
                "exact-shared-timestamp spot/perp price panel",
                "realized funding rows with source timestamps",
                "normalized dataset SHA256",
                "coverage bounds and missingness report",
            ),
            screen_may_read_protected_oos=boolean(),
        ),
        "signal_rules": _section(
            funding_history=token("three most recent realized funding payments available strictly before decision time"),
            direction_gate=token("all three realized funding rates > 0"),
            carry_gate=token("sum(last_3_realized_funding_bps) / 3 > frozen_two_leg_round_trip_cost_bps / 3"),
            basis_guard=token("abs(perp_close/spot_close-1) <= 0.50%"),
            decision_time=token("first completed 1h bar after a realized funding timestamp"),
            future_funding_rate_usage=token("forbidden"),
        ),
        "execution_rules": _section(
            entry=token("next completed 1h bar open after signal"),
            legs=token("long spot 1.0 notional and short perpetual 1.0 notional in same base asset"),
            hold=token("until first completed 1h bar after the next realized funding payment"),
            exit=token("close both legs at that bar open"),
            overlap=token("one hedge per base asset; no overlapping carry positions"),
            borrow_assumption=token("none; only positive-funding long-spot/short-perp direction is permitted"),
        ),
        "cost_model": COMMON_COST,
    },
    "TEST_SYNTHETIC_LIQUIDITY_V1": {
        "data_contract": _section(
            source=token("public timestamped venue data"),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
        ),
        "signal_rules": _section(
            shock_definition=token("frozen before outcomes"),
            entry_condition=token(
                "frozen before outcomes",
                "independent materially different frozen rule",
                "post-outcome rescue rule",
            ),
        ),
        "execution_rules": _section(
            entry_delay_bars=number(),
            exit_rule=token("fixed_holding_window"),
            position_overlap=token("forbidden"),
        ),
        "cost_model": TEST_COST,
    },
    "TEST_BEHAVIOR_IDENTITY_V1": {
        "data_contract": _section(source=token("public timestamped venue data"), point_in_time=boolean()),
        "signal_rules": _section(threshold=number(), entry_condition=token("frozen before outcomes")),
        "execution_rules": _section(entry_delay_bars=number(), exit_rule=token("fixed_holding_window")),
        "cost_model": TEST_COST,
    },
    "TEST_FIELD_SEMANTICS_V1": {
        "data_contract": _section(
            source=token("public timestamped venue data"),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
        ),
        "signal_rules": _section(
            threshold=number(),
            entry_condition=token(
                "frozen before outcomes",
                "abs(residual_zscore) >= 2.0 and liquidity < 1e6",
            ),
        ),
        "execution_rules": _section(entry_delay_bars=number(), exit_rule=token("fixed_holding_window")),
        "cost_model": TEST_COST,
    },
    "TEST_IDENTITY_PERMUTATION_V1": {
        "data_contract": _section(
            source=token("public timestamped venue data"),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
            fixed_instruments=instrument_set(),
        ),
        "signal_rules": _section(
            entry_condition=token("frozen before outcomes"),
            ordered_sequence=ordered_tokens("first", "second"),
        ),
        "execution_rules": _section(entry_delay_bars=number(), exit_rule=token("fixed_holding_window")),
        "cost_model": TEST_COST,
    },
    "TEST_IDENTITY_PERMUTATION_SYMBOLS_V1": {
        "data_contract": _section(
            source=token("public timestamped venue data"),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
            fixed_instruments=instrument_set(),
            symbols=symbol_set(),
        ),
        "signal_rules": _section(
            entry_condition=token("frozen before outcomes"),
            ordered_sequence=ordered_tokens("first", "second"),
        ),
        "execution_rules": _section(entry_delay_bars=number(), exit_rule=token("fixed_holding_window")),
        "cost_model": TEST_COST,
    },
    "TEST_IDENTITY_PERMUTATION_CARRYSETS_V1": {
        "data_contract": _section(
            source=token("public timestamped venue data"),
            point_in_time=boolean(),
            historical_universe=token("fixed_predeclared_assets"),
            fixed_instruments=instrument_set(),
            spot_hedges=instrument_set(),
            required_freeze_before_screen=token_set(
                "exact-shared-timestamp spot/perp price panel",
                "realized funding rows with source timestamps",
                "normalized dataset SHA256",
                "coverage bounds and missingness report",
            ),
        ),
        "signal_rules": _section(
            entry_condition=token("frozen before outcomes"),
            ordered_sequence=ordered_tokens("first", "second"),
        ),
        "execution_rules": _section(entry_delay_bars=number(), exit_rule=token("fixed_holding_window")),
        "cost_model": TEST_COST,
    },
}


def _validate_number(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(
            f"{path} must use a native JSON number under value contract v{BEHAVIOR_VALUE_CONTRACT_VERSION}"
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise RuntimeError(f"{path} must be finite")


def _validate_canonical_utc(value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise RuntimeError(f"{path} must be a canonical UTC timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{path} must be a canonical UTC timestamp string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeError(f"{path} must be UTC")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    if value != canonical:
        raise RuntimeError(f"{path} must use canonical UTC representation {canonical!r}")


def _validate_rule(value: Any, rule: ValueRule, path: str) -> None:
    if rule.kind == _NUMBER:
        _validate_number(value, path)
        return
    if rule.kind == _BOOL:
        if not isinstance(value, bool):
            raise RuntimeError(f"{path} must use a native JSON boolean")
        return
    if rule.kind == _NULL:
        if value is not None:
            raise RuntimeError(f"{path} must be null")
        return
    if rule.kind == _CLOSED_LITERAL:
        if not isinstance(value, str) or value not in rule.tokens:
            raise RuntimeError(f"{path} contains an unrecognized closed behavior token")
        return
    if rule.kind == _INSTRUMENT:
        if not isinstance(value, str) or not _INSTRUMENT_RE.fullmatch(value):
            raise RuntimeError(f"{path} must be a canonical uppercase instrument identifier")
        return
    if rule.kind == _SHA256:
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise RuntimeError(f"{path} must be a lowercase SHA-256 hex digest")
        return
    if rule.kind == _UTC_TIMESTAMP:
        _validate_canonical_utc(value, path)
        return
    if rule.kind == _NUMBER_LIST:
        if not isinstance(value, list) or not value:
            raise RuntimeError(f"{path} must be a non-empty numeric list")
        for index, item in enumerate(value):
            _validate_number(item, f"{path}[{index}]")
        return
    if rule.kind in {_INSTRUMENT_SET, _SYMBOL_SET, _CLOSED_LITERAL_SET, _ORDERED_LITERAL_LIST}:
        if not isinstance(value, list) or not value:
            raise RuntimeError(f"{path} must be a non-empty list")
        if not all(isinstance(item, str) for item in value):
            raise RuntimeError(f"{path} must contain strings")
        if len(set(value)) != len(value):
            raise RuntimeError(f"{path} must not contain duplicates")
        for item in value:
            if rule.kind == _INSTRUMENT_SET and not _INSTRUMENT_RE.fullmatch(item):
                raise RuntimeError(f"{path} contains a non-canonical instrument identifier")
            if rule.kind == _SYMBOL_SET and not _SYMBOL_RE.fullmatch(item):
                raise RuntimeError(f"{path} contains a non-canonical symbol identifier")
            if rule.kind in {_CLOSED_LITERAL_SET, _ORDERED_LITERAL_LIST} and item not in rule.tokens:
                raise RuntimeError(f"{path} contains an unrecognized closed behavior token")
        if rule.kind == _CLOSED_LITERAL_SET and set(value) != set(rule.tokens):
            raise RuntimeError(f"{path} must contain the exact reviewed closed-token set")
        return
    raise RuntimeError(f"unsupported behavior value rule kind {rule.kind!r} for {path}")


def _validate_registry_completeness() -> None:
    if set(BEHAVIOR_VALUE_CONTRACTS) != set(BEHAVIOR_SCHEMAS):
        missing = sorted(set(BEHAVIOR_SCHEMAS) - set(BEHAVIOR_VALUE_CONTRACTS))
        extra = sorted(set(BEHAVIOR_VALUE_CONTRACTS) - set(BEHAVIOR_SCHEMAS))
        raise RuntimeError(
            f"behavior value-contract schema coverage mismatch: missing={missing}, extra={extra}"
        )
    for schema_id, shape in BEHAVIOR_SCHEMAS.items():
        contract = BEHAVIOR_VALUE_CONTRACTS[schema_id]
        if set(contract) != set(BEHAVIOR_SECTIONS):
            raise RuntimeError(f"behavior value contract {schema_id} section coverage mismatch")
        for section in BEHAVIOR_SECTIONS:
            expected = set(shape[section])
            actual = set(contract[section])
            if actual != expected:
                raise RuntimeError(
                    f"behavior value contract {schema_id}.{section} field coverage mismatch: "
                    f"missing={sorted(expected-actual)}, extra={sorted(actual-expected)}"
                )


_validate_registry_completeness()


def validate_behavior_value_contract(candidate: dict[str, Any], schema_id: str) -> None:
    contract = BEHAVIOR_VALUE_CONTRACTS.get(schema_id)
    if contract is None:
        raise RuntimeError(f"no executable value contract for behavior schema {schema_id!r}")
    for section in BEHAVIOR_SECTIONS:
        values = candidate.get(section)
        if not isinstance(values, dict):
            raise RuntimeError(f"{section} must be an object for behavior value contract")
        for field, rule in contract[section].items():
            _validate_rule(values.get(field), rule, f"{section}.{field}")


def validate_target_value_contract(candidate: dict[str, Any], schema_id: str) -> None:
    markets = candidate.get("target_markets")
    if not isinstance(markets, list) or not markets:
        raise RuntimeError("target_markets must be a non-empty list")
    if len(set(markets)) != len(markets) or not all(isinstance(item, str) for item in markets):
        raise RuntimeError("target_markets must contain unique strings")
    if schema_id == "C101_DELTA_CARRY_V1":
        expected = {"BTC-USDT spot+swap", "ETH-USDT spot+swap", "SOL-USDT spot+swap"}
        if set(markets) != expected:
            raise RuntimeError("target_markets must use the exact reviewed delta-carry market tokens")
    else:
        for market in markets:
            if not _INSTRUMENT_RE.fullmatch(market):
                raise RuntimeError("target_markets must use canonical uppercase instrument identifiers")

    timeframes = candidate.get("target_timeframes")
    if not isinstance(timeframes, list) or not timeframes:
        raise RuntimeError("target_timeframes must be a non-empty list")
    if len(set(timeframes)) != len(timeframes):
        raise RuntimeError("target_timeframes must not contain duplicates")
    for timeframe in timeframes:
        if not isinstance(timeframe, str) or not _TIMEFRAME_RE.fullmatch(timeframe):
            raise RuntimeError("target_timeframes must use canonical lower-case timeframe tokens")

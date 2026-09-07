from copy import deepcopy

import pytest

from strategy_registry import (
    StrategyIdentityError,
    build_strategy_identity,
    strategy_fingerprint,
)


RULES = {
    "entry": {"ema_fast": 20, "ema_slow": 50, "minimum_slope_pct": 0.04},
    "allow_short": True,
    "risk_atr_multiple": 1.55,
}
EXECUTION = {
    "entry_timing": "next_bar_open",
    "fee_bps_round_trip": 10.0,
    "slippage_bps_round_trip": 4.0,
    "max_holding_bars": 24,
    "same_bar_stop_precedence": True,
}


def fingerprint(rules=RULES, execution=EXECUTION, **overrides):
    definition = {
        "symbol": "ETH-USDT",
        "horizon": "1H",
        "strategy_family": "trend",
        "rule_parameters": rules,
        "execution_assumptions": execution,
    }
    definition.update(overrides)
    return strategy_fingerprint(**definition)


def test_identical_definitions_have_stable_identity_regardless_of_mapping_order():
    first = build_strategy_identity(
        "ETH-USDT", "1H", "trend", RULES, EXECUTION
    )
    reordered = build_strategy_identity(
        "ETH-USDT",
        "1H",
        "trend",
        {
            "risk_atr_multiple": 1.55,
            "allow_short": True,
            "entry": {"minimum_slope_pct": 0.04, "ema_slow": 50, "ema_fast": 20},
        },
        {
            "same_bar_stop_precedence": True,
            "max_holding_bars": 24,
            "slippage_bps_round_trip": 4.0,
            "fee_bps_round_trip": 10.0,
            "entry_timing": "next_bar_open",
        },
    )

    assert first == reordered
    assert len(first.fingerprint) == 64


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("symbol", "BTC-USDT"),
        ("horizon", "4H"),
        ("strategy_family", "momentum"),
    ],
)
def test_identity_changes_when_a_core_definition_field_changes(field, changed):
    assert fingerprint() != fingerprint(**{field: changed})


@pytest.mark.parametrize(
    ("section", "field", "changed"),
    [
        ("rule", "allow_short", False),
        ("rule", "risk_atr_multiple", 1.56),
        ("execution", "entry_timing", "next_bar_close"),
        ("execution", "fee_bps_round_trip", 10.1),
        ("execution", "slippage_bps_round_trip", 4.1),
        ("execution", "max_holding_bars", 25),
        ("execution", "same_bar_stop_precedence", False),
    ],
)
def test_identity_changes_when_any_material_rule_or_execution_field_changes(
    section, field, changed
):
    rules = deepcopy(RULES)
    execution = deepcopy(EXECUTION)
    target = rules if section == "rule" else execution
    target[field] = changed

    assert fingerprint() != fingerprint(rules, execution)


def test_identity_changes_when_nested_rule_changes():
    rules = deepcopy(RULES)
    rules["entry"]["ema_fast"] = 21
    assert fingerprint() != fingerprint(rules=rules)


@pytest.mark.parametrize(
    "overrides",
    [
        {"symbol": None},
        {"symbol": " eth-usdt"},
        {"symbol": "ETH/USDT"},
        {"horizon": None},
        {"horizon": "1h"},
        {"horizon": "5m"},
        {"strategy_family": None},
        {"strategy_family": "Trend"},
        {"strategy_family": "unsupported"},
        {"rule_parameters": {}},
        {"rule_parameters": {"EMAFast": 20}},
        {"rule_parameters": {"ema_fast": None}},
        {"rule_parameters": {"levels": (1, 2)}},
        {"execution_assumptions": {}},
        {"execution_assumptions": {"fee_bps": float("nan")}},
        {"execution_assumptions": {"model": " next_bar_open"}},
    ],
)
def test_missing_malformed_noncanonical_or_unsupported_inputs_fail_closed(overrides):
    with pytest.raises(StrategyIdentityError):
        fingerprint(**overrides)

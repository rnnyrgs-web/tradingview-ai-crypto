import math

import pytest

from strategy_registry import strategy_identity_digest


BASE_RULES = {
    "fast_period": 20,
    "slow_period": 50,
    "entry": {"minimum_slope": 0.04, "directions": ["LONG", "SHORT"]},
}


def identity(**changes):
    inputs = {
        "symbol": "ETH-USDT",
        "horizon": "1H",
        "strategy_family": "trend",
        "rule_parameters": BASE_RULES,
    }
    inputs.update(changes)
    return strategy_identity_digest(**inputs)


def test_rule_dictionary_order_does_not_change_digest():
    reordered = {
        "entry": {"directions": ["LONG", "SHORT"], "minimum_slope": 0.04},
        "slow_period": 50,
        "fast_period": 20,
    }

    assert identity() == identity(rule_parameters=reordered)
    assert len(identity()) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"rule_parameters": {**BASE_RULES, "fast_period": 21}},
        {"symbol": "SOL-USDT"},
        {"horizon": "4H"},
        {"strategy_family": "momentum"},
    ],
)
def test_each_identity_component_changes_digest(change):
    assert identity(**change) != identity()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("symbol", None),
        ("symbol", ""),
        ("symbol", "eth-usdt"),
        ("symbol", "UNKNOWN"),
        ("horizon", None),
        ("horizon", "1h"),
        ("horizon", "unknown"),
        ("strategy_family", None),
        ("strategy_family", "Trend"),
        ("strategy_family", "unknown"),
        ("rule_parameters", None),
        ("rule_parameters", {}),
        ("rule_parameters", []),
        ("rule_parameters", {"threshold": math.nan}),
        ("rule_parameters", {"threshold": math.inf}),
        ("rule_parameters", {"threshold": -math.inf}),
        ("rule_parameters", {"threshold": None}),
        ("rule_parameters", {"bad-key": 1}),
        ("rule_parameters", {"threshold": object()}),
        ("rule_parameters", {"levels": []}),
    ],
)
def test_invalid_identity_inputs_fail_closed(field, invalid):
    with pytest.raises((TypeError, ValueError)):
        identity(**{field: invalid})


def test_cyclic_rule_parameters_fail_closed():
    rules = {"period": 20}
    rules["nested"] = rules

    with pytest.raises(ValueError, match="cycle"):
        identity(rule_parameters=rules)

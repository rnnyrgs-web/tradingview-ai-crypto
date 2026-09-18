import pytest

from research_engines.availability import engine_availability, require_engine
from research_engines.contract import CrossEngineContract
from research_engines.protocol import reconcile
from research_engines.signals import lagged_signals


def test_capabilities_never_grant_authority():
    state = engine_availability()
    assert {"vectorbt", "nautilus", "lean"} <= set(state)
    for engine in state.values():
        assert engine["research_only"] is True
        assert engine["trade_authority"] is False
        assert engine["promotion_authority"] is False


def test_unknown_engine_fails_closed():
    with pytest.raises(ValueError):
        require_engine("magic-profit-engine")


def test_contract_requires_frozen_identity_and_next_bar_execution():
    with pytest.raises(ValueError):
        CrossEngineContract("", "BTC-USDT", "1H", "trend", "abc", 10).canonical()
    with pytest.raises(ValueError):
        CrossEngineContract(
            "strategy", "BTC-USDT", "1H", "trend", "data", 10, 0
        ).canonical()



def test_contract_freezes_direction_sizing_capital_and_execution_conventions():
    base = dict(
        strategy_fingerprint="strategy",
        symbol="BTC-USDT",
        timeframe="1H",
        strategy_family="trend",
        data_fingerprint="data",
        cost_bps_round_trip=10,
    )
    with pytest.raises(ValueError):
        CrossEngineContract(**base, direction="sideways").canonical()
    with pytest.raises(ValueError):
        CrossEngineContract(**base, validation_quantity=0).canonical()
    with pytest.raises(ValueError):
        CrossEngineContract(**base, validation_initial_capital=0).canonical()
    with pytest.raises(ValueError):
        CrossEngineContract(
            **base, execution_price_model="same_bar_open"
        ).canonical()
    with pytest.raises(ValueError):
        CrossEngineContract(**base, timestamp_unit="ms").canonical()


def test_signal_path_conflicts_fail_closed_after_lag():
    contract = CrossEngineContract(
        "strategy", "BTC-USDT", "1H", "trend", "data", 10, 1
    )
    with pytest.raises(ValueError, match="entry/exit conflict"):
        lagged_signals(
            contract,
            [True, False, False],
            [True, False, False],
        )


def test_decision_path_is_shifted_before_any_engine_executes():
    contract = CrossEngineContract(
        "strategy", "BTC-USDT", "1H", "trend", "data", 10, 1
    )
    entries, exits = lagged_signals(
        contract,
        [True, False, False, False],
        [False, False, True, False],
    )
    assert entries == [False, True, False, False]
    assert exits == [False, False, False, True]


def test_decisions_falling_beyond_dataset_are_not_backfilled():
    contract = CrossEngineContract(
        "strategy", "BTC-USDT", "1H", "trend", "data", 10, 2
    )
    entries, exits = lagged_signals(
        contract,
        [False, False, False, True],
        [False, False, True, False],
    )
    assert entries == [False, False, False, False]
    assert exits == [False, False, False, False]


def test_reconciliation_requires_all_engines_same_contract():
    good = {
        "ok": True,
        "contract_fingerprint": "same",
        "metrics": {
            "trades": 0,
            "avg_trade_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "return_pct": 0.0,
            "win_rate": 0.0,
            "ending_equity": 100000.0,
        },
        "trades": [],
    }
    result = reconcile({"vectorbt": good, "nautilus": good})
    assert result["ok"] is False
    assert result["status"] == "WAIT_RESEARCH_ONLY"
    assert result["missing_engines"] == ["lean"]

    result = reconcile(
        {
            "vectorbt": good,
            "nautilus": good,
            "lean": {**good, "contract_fingerprint": "different"},
        }
    )
    assert result["ok"] is False
    assert result["same_contract"] is False


def test_reconciliation_fails_on_trade_path_disagreement():
    base = {
        "ok": True,
        "contract_fingerprint": "same",
        "metrics": {
            "trades": 1,
            "avg_trade_pct": 0.1,
            "max_drawdown_pct": 0.0,
            "return_pct": 0.1,
            "win_rate": 1.0,
            "ending_equity": 100100.0,
        },
        "trades": [
            {
                "direction": "long",
                "entry_ts": 1,
                "exit_ts": 2,
                "entry_price": 10.0,
                "exit_price": 11.0,
                "size": 100.0,
                "fees": 1.0,
                "pnl": 99.0,
            }
        ],
    }
    altered = {
        **base,
        "trades": [{**base["trades"][0], "exit_price": 11.5}],
    }
    result = reconcile({name: {**value, "engine": name, "research_only": True,
                               "trade_authority": False, "promotion_authority": False}
                        for name, value in (("vectorbt", base), ("nautilus", base), ("lean", altered))})
    assert result["ok"] is False
    assert "lean:trade[0].exit_price" in result["mismatches"]


@pytest.mark.parametrize("field,value", [
    ("cost_bps_round_trip", float("nan")),
    ("cost_bps_round_trip", float("inf")),
    ("validation_quantity", float("nan")),
    ("validation_initial_capital", float("inf")),
    ("decision_lag_bars", 1.5), ("decision_lag_bars", True),
    ("symbol", " "), ("timeframe", ""), ("strategy_family", ""),
])
def test_malformed_contract_cannot_receive_a_fingerprint(field, value):
    from dataclasses import replace

    frozen = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", "data", 10)
    with pytest.raises(ValueError):
        replace(frozen, **{field: value}).fingerprint()


def valid_engine_results():
    from research_engines.evidence import evidence

    frozen = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", "data", 10)
    trade = {"direction": "long", "entry_ts": 1, "exit_ts": 2,
             "entry_price": 100.0, "exit_price": 102.0, "size": 1.0,
             "fees": 0.1, "pnl": 1.9}
    return {name: evidence(name, frozen, [dict(trade)])
            for name in ("vectorbt", "nautilus", "lean")}


@pytest.mark.parametrize("field,value", [
    ("trades", [None]), ("trades", [{}]), ("trades", "invalid"),
    ("metrics", None), ("metrics", []), ("metrics", "invalid"),
    ("engine", "vectorbt"), ("research_only", False),
    ("trade_authority", True), ("promotion_authority", True),
    ("contract_fingerprint", 123),
])
def test_reconciliation_rejects_malformed_or_misattributed_evidence(field, value):
    results = valid_engine_results()
    results["lean"][field] = value
    result = reconcile(results)
    assert result["ok"] is False
    assert result["status"] == "WAIT_RESEARCH_ONLY"
    assert "lean" in result["invalid_engines"]
    assert result["promotion_authority"] is False


@pytest.mark.parametrize("field,value", [
    ("entry_ts", 2), ("entry_ts", 1.5), ("exit_ts", True),
    ("entry_price", -1), ("size", 0), ("fees", -1),
    ("pnl", float("nan")), ("direction", "sideways"),
])
def test_identical_invalid_trade_paths_do_not_count_as_agreement(field, value):
    results = valid_engine_results()
    for evidence_ in results.values():
        evidence_["trades"][0][field] = value
    result = reconcile(results)
    assert result["ok"] is False
    assert set(result["invalid_engines"]) == set(results)


@pytest.mark.parametrize("field,value", [
    ("trades", 2), ("trades", True), ("ending_equity", "invalid"),
    ("win_rate", 1.1), ("return_pct", float("inf")),
    ("ending_equity", 10 ** 400),
])
def test_invalid_metrics_fail_closed_even_when_all_engines_agree(field, value):
    results = valid_engine_results()
    for evidence_ in results.values():
        evidence_["metrics"][field] = value
    assert reconcile(results)["status"] == "WAIT_RESEARCH_ONLY"


@pytest.mark.parametrize("required", [(), ("vectorbt",), ("vectorbt", "vectorbt")])
def test_reconciliation_requires_distinct_independent_engines(required):
    assert reconcile(valid_engine_results(), required=required)["ok"] is False


def test_expected_contract_prevents_agreement_on_a_different_experiment():
    results = valid_engine_results()
    assert reconcile(results, expected_contract_fingerprint="different")["ok"] is False


def test_infinite_tolerance_cannot_suppress_disagreement():
    results = valid_engine_results()
    results["lean"]["trades"][0]["exit_price"] = 1000.0
    assert reconcile(results, price_tolerance=float("inf"))["ok"] is False

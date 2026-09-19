"""Hand-calculated financial and evidence-firewall examples; no market data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math

import pytest

from profitability_learning.analytics import analyze
from profitability_learning.contracts import fingerprint, validate_experiment


def component(kind="entry", rule="lagged_price_breakout"):
    return {"kind": kind, "rule": rule, "parameters": {"window": 20},
            "economic_reason": "Delayed information diffusion can sustain directional demand."}


def experiment(pnls=(10, -5, 20), *, split="DEVELOPMENT", name="sample"):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stamp = lambda days: (start + timedelta(days=days)).isoformat()
    strategy = {"mechanism": "information_diffusion", "components": [component()],
                "assets": ["BTC"], "timeframe": "1d", "execution_rule": "next_open"}
    contract = {"schema_version": 1, "strategy": strategy,
                "strategy_fingerprint": fingerprint(strategy), "family": "momentum",
                "dataset_id": name, "dataset_sha256": "a" * 64,
                "split": split, "start": stamp(0), "end": stamp(len(pnls) + 1),
                "frozen_at": stamp(-1), "outcomes_observed_at": stamp(len(pnls) + 2),
                "initial_capital": 1000.0, "cost_model": "fee_spread_slippage_carry_v1",
                "no_external_flows": True, "closed_portfolio": True,
                "point_in_time_verified": True, "provenance_ref": "fixture:audited",
                "minimum_events": 3, "search_budget": 8,
                "mining_dimensions": ["regime"], "max_feature_age_seconds": 86400,
                "ablation_components": [], "interaction_pairs": [],
                "purge_seconds": 0, "embargo_seconds": 86400}
    equity = [{"timestamp": stamp(0), "nav": 1000.0, "gross_exposure": 0.0}]
    trades = []
    nav = 1000.0
    for i, pnl in enumerate(pnls):
        nav += pnl
        trades.append({"trade_id": str(i), "event_id": str(i), "entry_at": stamp(i + 0.1),
                       "decision_at": stamp(i), "exit_at": stamp(i + 1),
                       "gross_pnl": pnl + 2, "costs": {"fees": 1, "spread": .5,
                       "slippage": .5, "funding_carry": 0}, "notional": 100,
                       "asset": "BTC", "timeframe": "1d", "direction": "LONG",
                       "features": {"regime": {"value": "trend" if i % 2 == 0 else "flat",
                                                "available_at": stamp(i)}}})
        equity.append({"timestamp": stamp(i + 1), "nav": nav, "gross_exposure": 100.0})
    equity.append({"timestamp": contract["end"], "nav": nav, "gross_exposure": 0})
    return {"contract": contract, "status": "REJECTED", "trades": trades,
            "equity": equity, "limitations": [], "failure_reasons": ["negative baseline comparison"]}


def test_compounded_return_reconciles_money_and_costs():
    result = analyze(experiment())
    assert result["metrics"]["compounded_net_return"] == pytest.approx(.025)
    assert result["metrics"]["net_pnl"] == 25
    assert result["metrics"]["max_drawdown"] == pytest.approx(5 / 1010)
    assert result["metrics"]["after_cost_expectancy_money"] == pytest.approx(25 / 3)
    assert result["metrics"]["cagr"] is None
    assert result["metrics"]["costs"]["fees"] == 3
    groups = result["attribution"]["regime"]
    assert groups["trend"]["net_pnl"] == 30
    assert groups["flat"]["net_pnl"] == -5
    assert sum(g["contribution_to_initial_capital"] for g in groups.values()) == pytest.approx(.025)
    assert result["trade_authority"] is False


def test_high_win_rate_with_catastrophic_loss_is_bad():
    result = analyze(experiment([10] * 9 + [-900]))
    assert result["metrics"]["win_rate_diagnostic"] == .9
    assert result["metrics"]["compounded_net_return"] == pytest.approx(-.81)
    assert "CATASTROPHIC_LOSS" in result["risk_flags"]
    assert result["economic_assessment"] == "NEGATIVE_AFTER_COST"


def test_one_lucky_trade_dominates_apparent_success():
    result = analyze(experiment([-5] * 9 + [100]))
    assert "SINGLE_WINNER_DEPENDENCE" in result["risk_flags"]
    assert result["concentration"]["net_pnl_without_best_trade"] == -45
    assert result["concentration"]["largest_winner_share"] == 1


def test_nav_not_product_of_overlapping_trade_returns():
    e = experiment([100, 100])
    e["trades"][1]["entry_at"] = e["trades"][0]["entry_at"]
    e["trades"][1]["decision_at"] = e["trades"][0]["decision_at"]
    e["trades"][1]["features"] = deepcopy(e["trades"][0]["features"])
    result = analyze(e)
    assert result["metrics"]["compounded_net_return"] == pytest.approx(.2)
    assert result["metrics"]["independent_event_count"] == 1


@pytest.mark.parametrize("mutation", [
    lambda e: e["equity"][-1].update(nav=999),
    lambda e: e["trades"][0]["costs"].pop("slippage"),
    lambda e: e["trades"][0]["costs"].update(fees=-1),
    lambda e: e["trades"][0].update(gross_pnl=float("nan")),
    lambda e: e["equity"][1].update(nav=float("inf")),
    lambda e: e["contract"].update(point_in_time_verified="true"),
    lambda e: e["contract"].update(initial_capital=True),
    lambda e: e["contract"].update(search_budget=True),
    lambda e: e["contract"].update(frozen_at="2025-01-01T00:00:00+00:00"),
    lambda e: e["contract"].update(strategy_fingerprint="renamed"),
    lambda e: e["trades"][0]["features"]["regime"].update(available_at="2021-01-01T00:00:00+00:00"),
    lambda e: e["trades"][0]["features"]["regime"].update(available_at="2019-01-01T00:00:00+00:00"),
    lambda e: e["trades"][0].update(exit_at=e["trades"][0]["entry_at"]),
    lambda e: e["trades"].append(deepcopy(e["trades"][0])),
    lambda e: e["contract"].update(split="UNTOUCHED_OOS"),
])
def test_bad_evidence_fails_closed(mutation):
    e = experiment()
    mutation(e)
    with pytest.raises(ValueError):
        analyze(e)


def test_missing_nav_does_not_invent_compounding():
    e = experiment()
    e["equity"] = []
    with pytest.raises(ValueError, match="equity"):
        analyze(e)


def test_bankruptcy_and_zero_equity_do_not_crash_or_recover():
    result = analyze(experiment([0, -1000]))
    assert result["metrics"]["compounded_net_return"] == -1
    assert result["metrics"]["max_drawdown"] == 1
    assert "INSOLVENT" in result["risk_flags"]
    with pytest.raises(ValueError, match="insolven"):
        analyze(experiment([-1000, 10]))


def test_component_fingerprint_is_order_stable():
    c = component()
    assert fingerprint(c) == fingerprint(dict(reversed(list(c.items()))))


def test_oos_summary_requires_release_and_cannot_generate_learning():
    e = experiment(split="RELEASED_OOS")
    with pytest.raises(ValueError, match="release"):
        analyze(e)
    e["contract"]["release_ref"] = "review:independent-release-1"
    result = analyze(e)
    assert result["development_learning_allowed"] is False
    assert result["attribution"] == {}


def test_missing_features_do_not_create_invented_groups():
    e = experiment()
    for row in e["trades"]:
        row["features"] = {}
    r = analyze(e)
    assert "regime" not in r["attribution"]
    assert "capacity" in r["unavailable_metrics"]


def test_cost_sensitivity_is_not_a_new_backtest():
    r = analyze(experiment([1, 1, 1]))
    assert r["concentration"]["net_pnl_at_double_variable_cost"] == -3
    assert "COST_SENSITIVE" in r["risk_flags"]


def test_infra_failure_is_not_a_negative_strategy_observation():
    e = experiment()
    e.update(status="INFRA_DATA_FAILURE", trades=[], equity=[],
             failure_reasons=["Historical publication timestamps unavailable"])
    r = analyze(e)
    assert r["outcome"] == "INFRA_DATA_FAILURE"
    assert r["metrics"] == {}
    assert r["economic_assessment"] == "UNKNOWN"

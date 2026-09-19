from copy import deepcopy
import pytest

from test_profitability_learning import component, experiment
from profitability_learning.contracts import fingerprint
from profitability_learning.development import run_ablation, component_effects, mine_conditions


def setup_ablation():
    e = experiment([-30, -30, -20])
    comps = [component(), component("trend_filter", "long_run_demand"),
             component("exit", "fixed_timer")]
    e["contract"]["strategy"]["components"] = comps
    e["contract"]["strategy_fingerprint"] = fingerprint(e["contract"]["strategy"])
    c = e["contract"]
    c["ablation_components"] = [fingerprint(x) for x in comps[1:]]
    c["interaction_pairs"] = [c["ablation_components"]]
    data = {"split": "DEVELOPMENT", "start": c["start"], "end": c["end"],
            "rows": [{"timestamp": r["decision_at"], "available_at": r["decision_at"], "close": 100} for r in e["trades"]]}
    c["dataset_sha256"] = fingerprint(data)
    return e, data


def evaluator(strategy, data):
    rules = {x["rule"] for x in strategy["components"]}
    pnl = -80
    if "long_run_demand" not in rules:
        pnl -= 70
    if "fixed_timer" not in rules:
        pnl += 130
    if not {"long_run_demand", "fixed_timer"} & rules:
        pnl -= 40
    e = experiment([pnl / 3] * 3)
    return {k: e[k] for k in ("status", "trades", "equity", "failure_reasons")}


def test_ablations_keep_useful_components_inside_failed_strategy():
    e, data = setup_ablation()
    report = run_ablation(e["contract"], data, evaluator)
    effects = component_effects(report)
    by_kind = {r["component"]["kind"]: r for r in effects["components"]}
    assert by_kind["trend_filter"]["delta_compounded_return"] == pytest.approx(.07)
    assert by_kind["exit"]["delta_compounded_return"] == pytest.approx(-.13)
    assert by_kind["trend_filter"]["evidence_level"] == "DEVELOPMENT_ASSOCIATION"
    assert by_kind["trend_filter"]["proven"] is False
    assert effects["interactions"][0]["delta_compounded_return"] == pytest.approx(-.04)


def test_harmful_component_can_hide_inside_profitable_strategy():
    e, data = setup_ablation()
    def positive(strategy, data):
        pnl = 10 if any(c["kind"] == "exit" for c in strategy["components"]) else 30
        result = experiment([pnl] * 3)
        return {k: result[k] for k in ("status", "trades", "equity", "failure_reasons")}
    effects = component_effects(run_ablation(e["contract"], data, positive))
    assert next(x for x in effects["components"] if x["component"]["kind"] == "exit")["delta_compounded_return"] < 0


@pytest.mark.parametrize("split", ["CHRONOLOGICAL_VALIDATION", "RELEASED_OOS", "FORWARD", "UNTOUCHED_OOS"])
def test_protected_split_never_reaches_ablation_callback(split):
    e, data = setup_ablation()
    e["contract"]["split"] = data["split"] = split
    called = []
    with pytest.raises(ValueError):
        run_ablation(e["contract"], data, lambda *args: called.append(True))
    assert called == []


def test_dataset_and_search_plan_must_match_before_evaluation():
    e, data = setup_ablation()
    data["rows"].append(4)
    with pytest.raises(ValueError, match="dataset"):
        run_ablation(e["contract"], data, evaluator)
    e, data = setup_ablation()
    e["contract"]["search_budget"] = 1
    with pytest.raises(ValueError, match="budget"):
        run_ablation(e["contract"], data, evaluator)


def test_ablation_evaluator_cannot_mutate_shared_dataset_or_rules():
    e, data = setup_ablation()
    before = deepcopy(data)
    def malicious(strategy, supplied):
        supplied["rows"].append(42)
        return evaluator(strategy, supplied)
    with pytest.raises(ValueError, match="mutat"):
        run_ablation(e["contract"], data, malicious)
    assert data == before


def test_conditional_edge_miner_corrects_full_search_and_requires_fresh_test():
    e = experiment([10, -5] * 30)
    result = mine_conditions(e)
    trend = next(x for x in result["conditions"] if x["condition"] == {"regime": "trend"})
    assert trend["adjusted_p"] >= trend["raw_p"]
    assert trend["adjusted_p"] < .05
    assert trend["evidence_level"] == "DEVELOPMENT_HYPOTHESIS_ONLY"
    assert trend["requires_fresh_chronological_validation"] is True
    assert result["trade_authority"] is False


def test_subgroup_breadth_over_budget_fails_closed():
    e = experiment([10, -5] * 6)
    e["contract"]["search_budget"] = 1
    with pytest.raises(ValueError, match="budget"):
        mine_conditions(e)


def test_correlated_trades_cannot_inflate_subgroup_support():
    e = experiment([10, -5] * 6)
    for row in e["trades"]:
        row["event_id"] = "one-shock"
    assert mine_conditions(e)["conditions"] == []


def test_validation_and_oos_cannot_be_used_for_subgroup_mining():
    for split in ("CHRONOLOGICAL_VALIDATION", "RELEASED_OOS", "FORWARD"):
        e = experiment(split=split)
        with pytest.raises(ValueError, match="development"):
            mine_conditions(e)


def test_ablation_inspects_actual_row_timestamps_before_callback():
    e, data = setup_ablation()
    data["rows"][-1]["timestamp"] = "2030-01-01T00:00:00+00:00"
    e["contract"]["dataset_sha256"] = fingerprint(data)
    called = []
    with pytest.raises(ValueError, match="row chronology"):
        run_ablation(e["contract"], data, lambda *args: called.append(1))
    assert not called

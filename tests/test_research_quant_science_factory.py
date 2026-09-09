from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_quant_science_factory import MAX_PER_METHOD, build_quant_science_queue


def _priority(dimension, group, wrong_rate=0.5, independent_samples=30):
    return {
        "dimension": dimension,
        "group": group,
        "samples": independent_samples * 2,
        "independent_samples": independent_samples,
        "wrong_rate": wrong_rate,
        "research_question": f"Can {dimension}={group} support a restrictive challenger?",
        "requires_new_validation": True,
    }


def test_quant_science_factory_predeclares_safe_scientific_design():
    diagnostics = {"research_priorities": [_priority("score_band", "70-79")]}
    queue = build_quant_science_queue(diagnostics)
    assert queue["experiment_count"] == 1
    experiment = queue["experiments"][0]
    design = experiment["science_design"]
    assert design["research_method"] == "selective_abstention_calibration"
    assert design["primary_endpoint"] == "after_cost_selective_precision_on_untouched_oos"
    assert design["predeclared_search_budget"] == 1
    assert design["parameter_mining_allowed"] is False
    assert design["untouched_oos_reuse_allowed"] is False
    assert design["forward_evidence_pooled_with_oos"] is False
    assert design["abstention_first"] is True
    assert experiment["trade_authority"] is False
    assert experiment["promotion_authority"] is False


def test_quant_science_factory_caps_hypothesis_family_breadth():
    diagnostics = {
        "research_priorities": [
            _priority("score_band", f"band-{idx}", wrong_rate=0.9 - idx * 0.01, independent_samples=40)
            for idx in range(MAX_PER_METHOD + 5)
        ]
    }
    queue = build_quant_science_queue(diagnostics)
    assert queue["method_counts"]["selective_abstention_calibration"] == MAX_PER_METHOD
    assert queue["experiment_count"] == MAX_PER_METHOD


def test_scheduler_defers_blocked_natural_history_candidate():
    diagnostics = {
        "research_priorities": [
            _priority("market_regime", "TREND", wrong_rate=0.7, independent_samples=40),
            _priority("score_band", "70-79", wrong_rate=0.5, independent_samples=30),
        ]
    }
    queue = build_quant_science_queue(diagnostics)
    blocked = queue["experiments"][0]
    blocked["evidence_readiness"] = "BLOCKED_NATURAL_HISTORY_ACCUMULATION"
    plan = build_heavy_dispatch_plan(queue)
    assert plan["blocked_candidate_count"] == 1
    assert plan["selected_count"] == 1
    assert plan["selected"][0]["experiment_id"] != blocked["experiment_id"]
    assert plan["raises_heavy_concurrency"] is False


def test_scheduler_rejects_science_design_that_allows_oos_reuse():
    diagnostics = {"research_priorities": [_priority("score_band", "80-89")]}
    queue = build_quant_science_queue(diagnostics)
    queue["experiments"][0]["science_design"]["untouched_oos_reuse_allowed"] = True
    plan = build_heavy_dispatch_plan(queue)
    assert plan["selected_count"] == 0

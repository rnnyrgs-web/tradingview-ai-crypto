from research_heavy_experiment_scheduler import build_heavy_dispatch_plan


def _experiment(experiment_id, priority, samples=20):
    scaled = min(1.0, max(0.0, float(priority) / 100.0))
    return {
        "experiment_id": experiment_id,
        "information_priority": priority,
        "source_samples": samples,
        "source_independent_samples": samples,
        "dimension": "market_regime",
        "group": "TREND",
        "hypothesis": "A predeclared regime condition can reduce false signals.",
        "predicted_mechanism": "Trend-regime structure may improve selective directional precision.",
        "target_horizon": "both",
        "expected_signal_quality_effect": "Improve genuine BUY/SELL precision or WAIT quality after costs.",
        "evidence_needed": ["chronological backtest", "untouched OOS", "genuine forward evidence"],
        "falsification_criteria": ["no stable after-cost OOS improvement"],
        "chronological_oos_requirements": ["purged chronology", "untouched OOS not reused for tuning"],
        "realistic_cost_treatment": ["fees, spread and slippage before expectancy claims"],
        "independent_sample_requirements": ["non-overlapping full-horizon observations only"],
        "result": None,
        "evidence_conclusion": "unresolved",
        "priority_factors": {
            "expected_genuine_signal_quality_impact": scaled,
            "expected_information_falsification_value": 1.0,
            "probability_actionable_evidence": 1.0,
            "compute_api_cost_units": 1.0,
        },
        "compute_class": "heavy_candidate",
        "status": "QUEUED_RESEARCH_ONLY",
        "required_validation": ["untouched_oos", "realistic_cost_stress", "genuine_forward_shadow"],
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }


def test_scheduler_admits_highest_priority_without_raising_concurrency():
    queue = {"experiments": [_experiment("low", 10, 50), _experiment("high", 20, 15)]}
    plan = build_heavy_dispatch_plan(queue, max_slots=2)
    assert plan["heavy_slot_limit"] == 1
    assert plan["selected_count"] == 1
    assert plan["selected"][0]["experiment_id"] == "high"
    assert plan["raises_heavy_concurrency"] is False
    assert plan["trade_authority"] is False


def test_scheduler_skips_running_and_rejects_authority_escalation():
    unsafe = _experiment("unsafe", 100)
    unsafe["trade_authority"] = True
    queue = {"experiments": [unsafe, _experiment("running", 90), _experiment("safe", 80)]}
    plan = build_heavy_dispatch_plan(queue, running_experiment_ids=["running"])
    assert [item["experiment_id"] for item in plan["selected"]] == ["safe"]

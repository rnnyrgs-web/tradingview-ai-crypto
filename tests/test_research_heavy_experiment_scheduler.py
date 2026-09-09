from research_heavy_experiment_scheduler import build_heavy_dispatch_plan


def _experiment(experiment_id, priority, samples=20):
    return {
        "experiment_id": experiment_id,
        "information_priority": priority,
        "source_samples": samples,
        "dimension": "market_regime",
        "group": "TREND",
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

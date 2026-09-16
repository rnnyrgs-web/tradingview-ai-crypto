from research_validation import evaluate_candidate_stage, normalize_economic_result


def complete_evidence():
    return {
        "research": {"net_expectancy_pct": 0.20, "profit_factor": 1.20, "trades": 120, "chronology_safe": True},
        "validation": {"net_expectancy_pct": 0.15, "profit_factor": 1.15, "trades": 50, "chronology_safe": True},
        "robustness": {
            "parameter_neighborhood_stable": True,
            "cost_2x_positive": True,
            "cost_3x_acceptable": True,
            "not_single_trade_dominated": True,
            "not_single_asset_dominated": True,
        },
        "multiple_testing": {"pass": True},
        "dataset": {"certified": True},
        "oos": {"opened": True, "frozen_before_open": True, "net_expectancy_pct": 0.10, "profit_factor": 1.10, "trades": 40},
        "independent_reproduction": {"pass": True},
        "forward": {"observations": 0, "pass": False},
    }


def test_normalize_economic_result_uses_stable_schema():
    result = normalize_economic_result({"net_return": 12, "net_expectancy_pct": 0.2, "profit_factor": 1.4, "trades": 80})
    assert result["net_return"] == 12.0
    assert result["net_expectancy_pct"] == 0.2
    assert result["profit_factor"] == 1.4
    assert result["trade_count"] == 80
    assert "max_drawdown_pct" in result


def test_oos_survivor_waits_for_forward():
    result = evaluate_candidate_stage(complete_evidence())
    assert result["state"] == "FORWARD_PENDING"
    assert result["production_candidate"] is False
    assert result["real_money_trade_authority"] is False


def test_negative_oos_is_rejected():
    evidence = complete_evidence()
    evidence["oos"]["net_expectancy_pct"] = -0.01
    assert evaluate_candidate_stage(evidence)["state"] == "REJECTED"


def test_missing_independent_reproduction_blocks_after_oos_pass():
    evidence = complete_evidence()
    evidence["independent_reproduction"] = {"pass": False, "status": "UNAVAILABLE"}
    result = evaluate_candidate_stage(evidence)
    assert result["state"] == "OOS_PASS"
    assert "independent_reproduction" in result["blocking_gates"]


def test_forward_pass_never_grants_real_money_authority():
    evidence = complete_evidence()
    evidence["forward"] = {"observations": 30, "pass": True}
    result = evaluate_candidate_stage(evidence)
    assert result["state"] == "FORWARD_PASS"
    assert result["production_candidate"] is True
    assert result["real_money_trade_authority"] is False

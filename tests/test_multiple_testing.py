import multiple_testing as mt
from research_runner import declared_hypothesis_trials


def _strategy(prob=0.99, p05=2.0, val_trades=25, holdout_trades=25, eligible=True):
    return {
        "strategy_family": "trend",
        "status": "ROBUST_OOS" if eligible else "RESEARCH_ONLY",
        "eligible_for_promotion_review": eligible,
        "validation": {"trades": val_trades},
        "holdout_test": {"trades": holdout_trades},
        "quality_gate": {"reasons": []},
        "robustness": {
            "monte_carlo": {
                "probability_positive": prob,
                "p05_sum_returns_pct": p05,
            }
        },
    }


def test_requirements_increase_with_search_breadth():
    small = mt.evidence_requirements(6)
    large = mt.evidence_requirements(3000)
    assert large["min_combined_oos_trades"] > small["min_combined_oos_trades"]
    assert large["min_bootstrap_probability_positive"] > small["min_bootstrap_probability_positive"]
    assert large["min_bootstrap_probability_positive"] <= 0.99


def test_strong_deep_oos_can_pass_large_search_breadth():
    gate = mt.assess_strategy(_strategy(prob=0.995, p05=4.0, val_trades=30, holdout_trades=30), 3000)
    assert gate["passed"]
    assert not gate["can_authorize_by_itself"]


def test_old_style_thin_oos_is_rejected_when_many_hypotheses_were_tried():
    gate = mt.assess_strategy(_strategy(prob=0.90, p05=1.0, val_trades=8, holdout_trades=8), 3000)
    assert not gate["passed"]
    assert "insufficient_oos_depth_for_search_breadth" in gate["reasons"]
    assert "bootstrap_support_too_weak_for_search_breadth" in gate["reasons"]


def test_negative_bootstrap_lower_bound_always_fails():
    gate = mt.assess_strategy(_strategy(prob=0.999, p05=-0.01, val_trades=100, holdout_trades=100), 100)
    assert not gate["passed"]
    assert "bootstrap_lower_bound_not_positive" in gate["reasons"]


def test_registry_firewall_can_only_demote():
    result = {"registry": [_strategy(prob=0.85, p05=0.2, val_trades=10, holdout_trades=10, eligible=True)]}
    gated = mt.apply_registry_firewall(result, 3000)
    row = gated["registry"][0]
    assert not row["eligible_for_promotion_review"]
    assert row["status"] == "RESEARCH_ONLY"
    assert "multiple_testing_evidence_insufficient" in row["quality_gate"]["reasons"]
    assert result["registry"][0]["eligible_for_promotion_review"] is True


def test_registry_firewall_never_promotes_previously_ineligible_strategy():
    result = {"registry": [_strategy(prob=0.999, p05=10.0, val_trades=100, holdout_trades=100, eligible=False)]}
    gated = mt.apply_registry_firewall(result, 10)
    assert gated["registry"][0]["eligible_for_promotion_review"] is False


def test_trial_declaration_uses_full_universe_not_current_shard():
    count = declared_hypothesis_trials(
        ["BTC-USDT"],
        ["15m", "1H"],
        {"universe_size_resolved": 80, "shard_count": 8},
    )
    assert count == 80 * 2 * 6 * 3

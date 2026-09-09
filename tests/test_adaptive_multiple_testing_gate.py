from research_adaptive_accuracy import _multiple_testing_policy, _passes_validation


def test_sequential_alpha_spending_gets_stricter_as_trials_accumulate():
    first = _multiple_testing_policy({"conclusive_trial_count": 0})
    later = _multiple_testing_policy({"conclusive_trial_count": 24})
    assert first["trial_index"] == 1
    assert later["trial_index"] == 25
    assert later["alpha_this_trial"] < first["alpha_this_trial"]
    assert later["validation_confidence_z"] > first["validation_confidence_z"]
    assert first["oos_sealed_pending_gate"] is True


def test_point_lift_alone_cannot_open_oos_when_adjusted_confidence_is_weak():
    evaluation = {
        "baseline": {"precision": 0.60},
        "filtered": {
            "samples": 12,
            "precision": 0.75,
            "precision_multiple_testing_lower": 0.58,
            "after_cost_expectancy_pct": 0.25,
            "expectancy_sample_complete": True,
        },
        "precision_lift": 0.15,
        "actionable_coverage": 0.50,
    }
    science_design = {
        "minimum_effect_to_continue": {"precision_absolute_improvement": 0.02},
        "minimum_evaluation_samples": 8,
        "minimum_actionable_coverage": 0.25,
    }
    assert _passes_validation(evaluation, science_design) is False

    evaluation["filtered"]["precision_multiple_testing_lower"] = 0.61
    assert _passes_validation(evaluation, science_design) is True

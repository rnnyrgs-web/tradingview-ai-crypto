from strategy_mission_dashboard import build_mission_snapshot


def objective():
    return {
        "primary_mission": "Find one independently validated after-cost strategy",
        "single_strategy_focus": {
            "lifecycle_phase": "SELECTION",
            "active_candidate": None,
            "required_evidence": [
                "predeclared_immutable_fingerprint",
                "positive_after_cost_expectancy",
                "untouched_oos",
                "multiple_testing_control",
                "genuine_forward_paper_validation",
            ],
        },
    }


def test_mission_snapshot_exposes_full_scientific_funnel_fail_closed_when_coordinator_missing():
    snapshot = build_mission_snapshot(objective(), None)
    assert snapshot["funnel"] == {
        "ideas": "UNVERIFIED",
        "frozen_candidates": "UNVERIFIED",
        "validation_pass": "UNVERIFIED",
        "robustness_pass": "UNVERIFIED",
        "oos_pass": "UNVERIFIED",
        "forward_pass": "UNVERIFIED",
        "paper_champions": "UNVERIFIED",
    }
    assert snapshot["closest_candidate"] is None
    assert snapshot["negative_knowledge"]["status"] == "UNVERIFIED"
    assert snapshot["independent_reproduction"]["status"] == "UNVERIFIED"
    assert snapshot["multiple_testing"]["status"] == "UNVERIFIED"
    assert snapshot["cost_stress"]["status"] == "UNVERIFIED"
    assert snapshot["parameter_stability"]["status"] == "UNVERIFIED"
    assert snapshot["forward_evidence"]["status"] == "UNVERIFIED"


def test_mission_snapshot_uses_explicit_research_truth_without_inventing_missing_results():
    coordinator = {
        "ok": True,
        "broker_connected": False,
        "trade_authority": False,
        "worker_army": {"worker_count": 20, "heavy_worker_count": 18, "lightweight_worker_count": 2, "workers": {}, "supervisor": {"healthy": True}},
        "research_director": {"missions": []},
        "research_truth": {
            "funnel": {"ideas": 14, "frozen_candidates": 3, "validation_pass": 1, "robustness_pass": 0, "oos_pass": 0, "forward_pass": 0, "paper_champions": 0},
            "closest_candidate": {"strategy_fingerprint": "abc", "state": "VALIDATION_PASS", "blockers": ["robustness"]},
            "negative_knowledge": {"status": "VERIFIED", "rejected_count": 2},
            "independent_reproduction": {"status": "PENDING"},
            "multiple_testing": {"status": "PASS"},
            "cost_stress": {"status": "PENDING"},
            "parameter_stability": {"status": "PENDING"},
            "forward_evidence": {"status": "NOT_STARTED", "observations": 0},
            "experiment_activity": {"completed": 4, "rejected": 3, "promoted": 0, "insufficient_evidence": 1},
        },
    }
    snapshot = build_mission_snapshot(objective(), coordinator)
    assert snapshot["funnel"]["ideas"] == 14
    assert snapshot["closest_candidate"]["state"] == "VALIDATION_PASS"
    assert snapshot["missing_evidence"] == ["robustness"]
    assert snapshot["negative_knowledge"]["rejected_count"] == 2
    assert snapshot["experiment_activity"]["completed"] == 4

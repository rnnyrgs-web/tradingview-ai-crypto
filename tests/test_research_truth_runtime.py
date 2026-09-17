from __future__ import annotations

from research_truth import build_research_truth


def test_selection_truth_is_fail_closed_without_frozen_candidate():
    objective = {"single_strategy_focus": {"lifecycle_phase": "SELECTION", "active_candidate": None}}
    director = {"missions": [{"mission_id": "m1"}], "daily_lead_report": {"experiments": {"tested": 2, "rejected": 1}}}
    army = {"workers": {}}
    truth = build_research_truth(objective, director, army)
    assert truth["funnel"]["ideas"] == 1
    assert truth["funnel"]["frozen_candidates"] == 0
    assert truth["closest_candidate"] is None
    assert "candidate_not_frozen" in truth["missing_evidence"]


def test_truth_uses_only_active_fingerprint_canonical_evidence():
    fingerprint = "active-fp"
    objective = {
        "single_strategy_focus": {
            "lifecycle_phase": "DEEP_VALIDATION",
            "active_candidate": {"fingerprint_id": fingerprint},
        }
    }
    canonical = {
        "strategy_fingerprint": fingerprint,
        "decision": {
            "state": "OOS_PASS",
            "blocking_gates": ["independent_reproduction"],
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        },
        "evidence": {
            "multiple_testing": {"pass": True},
            "robustness": {
                "parameter_neighborhood_stable": True,
                "cost_2x_positive": True,
                "cost_3x_acceptable": True,
            },
            "independent_reproduction": {"pass": False, "status": "NOT_RUN"},
            "forward": {"pass": False, "status": "NOT_STARTED", "observations": 0},
        },
    }
    army = {
        "workers": {
            "major-btc": {"latest_evidence": {"canonical_candidate_results": [canonical]}},
            "stale": {"latest_evidence": {"canonical_candidate_results": [{**canonical, "strategy_fingerprint": "other"}]}},
        }
    }
    director = {"missions": [], "daily_lead_report": {"experiments": {"tested": 1, "rejected": 0}}}
    truth = build_research_truth(objective, director, army)
    assert truth["closest_candidate"]["strategy_fingerprint"] == fingerprint
    assert truth["closest_candidate"]["state"] == "OOS_PASS"
    assert truth["funnel"]["oos_pass"] == 1
    assert truth["funnel"]["forward_pass"] == 0
    assert truth["multiple_testing"]["status"] == "PASS"
    assert truth["independent_reproduction"]["status"] == "NOT_RUN"
    assert truth["missing_evidence"] == ["independent_reproduction"]


def test_rejected_active_candidate_is_visible_as_negative_knowledge():
    fingerprint = "rejected-fp"
    objective = {"single_strategy_focus": {"lifecycle_phase": "REJECTED", "active_candidate": {"fingerprint_id": fingerprint}}}
    canonical = {
        "strategy_fingerprint": fingerprint,
        "decision": {
            "state": "REJECTED",
            "blocking_gates": [],
            "rejection_reasons": ["oos_economics_failed"],
            "production_candidate": False,
            "real_money_trade_authority": False,
        },
        "evidence": {},
    }
    army = {"workers": {"worker": {"latest_evidence": {"canonical_candidate_results": [canonical]}}}}
    truth = build_research_truth(objective, {"missions": []}, army)
    assert truth["closest_candidate"]["state"] == "REJECTED"
    assert truth["negative_knowledge"]["status"] == "VERIFIED"
    assert truth["negative_knowledge"]["reasons"] == ["oos_economics_failed"]
    assert truth["funnel"]["paper_champions"] == 0

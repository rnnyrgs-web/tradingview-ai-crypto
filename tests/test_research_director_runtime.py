from research_director_runtime import refresh_director


def _army(workers):
    return {
        "worker_count": len(workers),
        "heavy_worker_count": 3,
        "lightweight_worker_count": 2,
        "active_jobs": sum(1 for row in workers.values() if row.get("state") in {"queued", "running"}),
        "completed_jobs": 12,
        "failed_jobs": 0,
        "workers": workers,
        "supervisor": {"healthy": True, "task_restarts": 0},
        "observability": {"workers": {"failed": 0, "timeouts": 0}},
    }


def test_refresh_director_builds_claims_and_preserves_no_authority():
    state = refresh_director(
        _army(
            {
                "adaptive-accuracy": {
                    "state": "running",
                    "latest_evidence": {
                        "evidence_conclusion": "pending_validation",
                        "experiment": {
                            "experiment_id": "exp-1",
                            "effective_horizon": "24h",
                            "dimension": "direction",
                            "group": "BUY",
                            "hypothesis": "abstain from weak BUY subgroup",
                            "validation_passed": False,
                        },
                        "oos_opened": False,
                    },
                },
                "learning-diagnostics": {"state": "resting", "latest_evidence": {}},
            }
        )
    )
    assert state["research_only"] is True
    assert state["trade_authority"] is False
    assert state["promotion_authority"] is False
    assert state["automatic_strategy_promotion"] is False
    assert len(state["missions"]) == 2
    assert len(state["claims"]) == 1
    assert state["claims"][0]["worker_id"] == "adaptive-accuracy"
    assert state["daily_lead_report"]["production_promotion_occurred"] is False


def test_pure_insufficient_history_is_blocked_and_yields_next_mission():
    state = refresh_director(
        _army(
            {
                "cross-asset-rank-24h": {
                    "state": "resting",
                    "latest_evidence": {
                        "research_blocked": True,
                        "failure_type_counts": {"InsufficientHistory": 3},
                        "universe_requested": 30,
                        "universe_resolved": 27,
                    },
                },
                "adaptive-accuracy": {
                    "state": "resting",
                    "latest_evidence": {"evidence_conclusion": "no_dispatchable_hypothesis"},
                },
            }
        )
    )
    blocked = next(m for m in state["missions"] if m["lane"] == "cross-asset")
    assert blocked["blocker"] == "InsufficientHistory"
    assert blocked["recheck_after"] is not None
    assert all(m["mission_id"] != blocked["mission_id"] for m in state["next_missions"])


def test_mixed_failure_is_not_misclassified_as_natural_history():
    state = refresh_director(
        _army(
            {
                "cross-asset-rank-7d": {
                    "state": "resting",
                    "latest_evidence": {
                        "research_blocked": True,
                        "failure_type_counts": {"InsufficientHistory": 12, "RequestError": 1},
                        "universe_requested": 30,
                        "universe_resolved": 17,
                    },
                }
            }
        )
    )
    mission = state["missions"][0]
    assert mission["blocker"] is None
    assert mission["recheck_after"] is None

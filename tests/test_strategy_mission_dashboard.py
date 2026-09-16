from __future__ import annotations

from strategy_mission_dashboard import build_mission_snapshot


def _objective(active_candidate=None, phase="SELECTION"):
    return {
        "primary_mission": "Find and validate one strategy with genuine sustainable after-cost profitability.",
        "single_strategy_focus": {
            "enabled": True,
            "lifecycle_phase": phase,
            "active_candidate": active_candidate,
            "required_evidence": [
                "predeclared_immutable_fingerprint",
                "positive_after_cost_expectancy",
                "untouched_oos",
                "genuine_forward_paper_validation",
            ],
            "real_money_trading_authority": False,
        },
    }


def _coordinator(latest_evidence=None, *, healthy=True):
    return {
        "ok": healthy,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
        "worker_army": {
            "worker_count": 3,
            "heavy_worker_count": 1,
            "lightweight_worker_count": 2,
            "supervisor": {
                "healthy": healthy,
                "stale_workers": [],
                "crashed_workers": [],
            },
            "workers": {
                "cross-asset-rank-24h": {
                    "state": "resting",
                    "latest_evidence": latest_evidence,
                },
                "learning-diagnostics": {"state": "running"},
                "experiment-factory": {"state": "running"},
            },
        },
        "research_director": {"missions": [{}, {}, {}]},
    }


def test_selection_blocker_is_explicit_and_oos_stays_locked():
    coordinator = _coordinator({
        "research_blocked": True,
        "research_blocked_reason": "insufficient_supported_liquidity_subsets",
        "untouched_oos_opened": False,
        "universe_requested": 30,
        "universe_resolved": 22,
        "supported_liquidity_subsets": [],
        "selected_oos": None,
    })

    snapshot = build_mission_snapshot(_objective(), coordinator)

    assert snapshot["strategy_status"] == "NO VALIDATED STRATEGY YET"
    assert snapshot["phase"] == "SELECTION"
    assert snapshot["candidate_fingerprint"] is None
    assert snapshot["oos_status"] == "LOCKED"
    assert snapshot["blocker"] == "insufficient_supported_liquidity_subsets"
    assert snapshot["coverage"] == "22/30"
    assert snapshot["focused_workers"] == 3
    assert snapshot["worker_health"] == "HEALTHY"
    assert snapshot["broker_status"] == "DISCONNECTED"


def test_frozen_candidate_shows_fingerprint_but_not_validated_without_evidence():
    fingerprint = "abc123"
    objective = _objective(
        active_candidate={
            "fingerprint_id": fingerprint,
            "deep_worker_contracts": {"cross-asset-rank-24h": {"strategy_family": "relative_strength"}},
        },
        phase="DEEP_VALIDATION",
    )
    coordinator = _coordinator({
        "research_blocked": False,
        "untouched_oos_opened": True,
        "selected_oos": {
            "candidate_fingerprint": fingerprint,
            "acc002_research_pass": False,
            "eligible_for_promotion_review": False,
        },
    })

    snapshot = build_mission_snapshot(objective, coordinator)

    assert snapshot["candidate_fingerprint"] == fingerprint
    assert snapshot["oos_status"] == "OPENED"
    assert snapshot["strategy_status"] == "NO VALIDATED STRATEGY YET"
    assert snapshot["promotion_status"] == "BLOCKED"


def test_missing_coordinator_state_fails_closed():
    snapshot = build_mission_snapshot(_objective(), None)

    assert snapshot["strategy_status"] == "NO VALIDATED STRATEGY YET"
    assert snapshot["worker_health"] == "UNVERIFIED"
    assert snapshot["oos_status"] == "LOCKED"
    assert snapshot["blocker"] == "coordinator_state_unavailable"
    assert snapshot["broker_status"] == "UNVERIFIED"


def test_validated_label_requires_explicit_complete_validation_state():
    fingerprint = "valid-fp"
    objective = _objective(
        active_candidate={
            "fingerprint_id": fingerprint,
            "validation_status": "VALIDATED_RESEARCH_CANDIDATE",
            "deep_worker_contracts": {"cross-asset-rank-24h": {"strategy_family": "relative_strength"}},
        },
        phase="FORWARD_VALIDATED",
    )
    coordinator = _coordinator({
        "research_blocked": False,
        "untouched_oos_opened": True,
        "selected_oos": {
            "candidate_fingerprint": fingerprint,
            "acc002_research_pass": True,
            "eligible_for_promotion_review": True,
        },
    })

    snapshot = build_mission_snapshot(objective, coordinator)

    assert snapshot["strategy_status"] == "VALIDATED RESEARCH CANDIDATE"
    assert snapshot["promotion_status"] == "RESEARCH VALIDATED — REAL MONEY STILL DISABLED"
    assert snapshot["broker_status"] == "DISCONNECTED"

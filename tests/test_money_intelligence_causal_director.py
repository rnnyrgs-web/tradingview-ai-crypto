from copy import deepcopy

import research_director_runtime as director
from research_director import build_mission


def _army():
    return {
        "worker_count": 0,
        "heavy_worker_count": 0,
        "lightweight_worker_count": 0,
        "active_jobs": 0,
        "completed_jobs": 0,
        "failed_jobs": 0,
        "workers": {},
        "supervisor": {"healthy": True, "task_restarts": 0},
        "observability": {"workers": {"failed": 0, "timeouts": 0}},
    }


def _causal_feedback(*, status="READY", missions=True):
    rows = []
    if missions:
        mission = build_mission(
            lane="big-move",
            horizon="72h",
            direction="BUY",
            theme="causal-repricing:pit-fingerprint",
            hypothesis="replicate and falsify frozen mechanism",
            expected_information_gain=0.88,
            expected_signal_impact=0.88,
            expected_profitability_impact=0.5,
            sample_readiness=0.5,
            novelty=0.75,
            falsification_value=0.95,
            actionable_evidence_probability=0.88,
            compute_cost=0.35,
            experiment_id="mi-causal-pit-v1:abc",
        ).to_dict()
        mission.update(
            {
                "causal_evidence": {
                    "memory_content_digest": "a" * 64,
                    "hypothesis_id": "H1",
                    "effective_fingerprint": "mi-causal-pit-v1:abc",
                    "event_fingerprints": ["mi-evidence-v1:def"],
                },
                "research_only": True,
                "trade_authority": False,
                "promotion_authority": False,
                "oos_opening_authority": False,
            }
        )
        rows.append(mission)
    return {
        "status": status,
        "as_of": "2026-09-03T01:00:00Z",
        "content_digest": "a" * 64 if status == "READY" else None,
        "missions": rows,
        "rejected_hypothesis_ids": [],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "oos_opening_authority": False,
        "broker_connected": False,
    }


def _configure(monkeypatch, tmp_path, feedback):
    monkeypatch.setattr(director, "causal_mission_feedback", lambda: deepcopy(feedback))
    monkeypatch.setattr(
        director,
        "probe_bybit_oi_access",
        lambda: {"status": "source_error", "points_observed": 0},
    )
    monkeypatch.setattr(director, "_STATE_PATH", tmp_path / "director.json")
    monkeypatch.setattr(director, "_bybit_probe_ran", False)
    monkeypatch.setattr(director, "_bybit_probe_result", None)


def test_durable_causal_evidence_enters_real_next_mission_ranking(monkeypatch, tmp_path):
    feedback = _causal_feedback()
    _configure(monkeypatch, tmp_path, feedback)

    state = director.refresh_director(_army())

    assert state["money_intelligence_causal_memory"] == feedback
    assert [row["lane"] for row in state["missions"]] == ["big-move"]
    assert [row["lane"] for row in state["next_missions"]] == ["big-move"]
    assert state["missions"][0]["causal_evidence"]["hypothesis_id"] == "H1"
    assert state["daily_lead_report"]["highest_priority_next_missions"] == state[
        "next_missions"
    ]
    assert state["trade_authority"] is False
    assert state["promotion_authority"] is False
    assert state["broker_connected"] is False


def test_narrative_only_causal_state_changes_no_eligibility(monkeypatch, tmp_path):
    feedback = _causal_feedback(missions=False)
    _configure(monkeypatch, tmp_path, feedback)

    state = director.refresh_director(_army())

    assert state["missions"] == []
    assert state["next_missions"] == []
    assert state["money_intelligence_causal_memory"]["status"] == "READY"


def test_causal_backend_outage_never_uses_stale_missions(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, _causal_feedback())
    assert director.refresh_director(_army())["next_missions"]

    unavailable = _causal_feedback(status="WAIT_MEMORY_UNAVAILABLE", missions=False)
    monkeypatch.setattr(
        director, "causal_mission_feedback", lambda: deepcopy(unavailable)
    )
    state = director.refresh_director(_army())

    assert state["money_intelligence_causal_memory"]["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert state["missions"] == []
    assert state["next_missions"] == []


def test_active_worker_claims_do_not_claim_causal_mission(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, _causal_feedback())
    army = _army()
    army["workers"] = {"learning-diagnostics": {"state": "running"}}

    state = director.refresh_director(army)

    causal_id = next(row["mission_id"] for row in state["missions"] if row["lane"] == "big-move")
    assert all(claim["mission_id"] != causal_id for claim in state["claims"])
    assert causal_id in {row["mission_id"] for row in state["next_missions"]}

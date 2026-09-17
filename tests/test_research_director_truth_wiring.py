from __future__ import annotations

import research_director_runtime as runtime


def test_refresh_director_publishes_fail_closed_research_truth(monkeypatch):
    monkeypatch.setattr(runtime, "_ensure_bybit_probe", lambda: {"status": "source_error"})
    objective = {
        "single_strategy_focus": {
            "lifecycle_phase": "SELECTION",
            "active_candidate": None,
        }
    }
    monkeypatch.setattr(runtime, "load_objective", lambda: objective)
    army = {
        "workers": {},
        "worker_count": 0,
        "heavy_worker_count": 0,
        "lightweight_worker_count": 0,
        "completed_jobs": 0,
        "failed_jobs": 0,
        "supervisor": {"task_restarts": 0},
        "observability": {"workers": {}},
    }
    result = runtime.refresh_director(army)
    assert result["research_truth"]["funnel"]["frozen_candidates"] == 0
    assert result["research_truth"]["missing_evidence"] == ["candidate_not_frozen"]
    assert result["research_truth"]["trade_authority"] is False

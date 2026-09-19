import copy
import gzip
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from profitability_learning.contracts import SAFE
from research_artifact import seal_research_payload
from test_profitability_learning_supabase import FakeSupabase


ARTIFACT = Path("orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz")
DEPLOYED_SHA = "5cf3f144820009619b5765355dc228cc05b26383"


@pytest.fixture
def durable_runtime(monkeypatch):
    import db

    fake = FakeSupabase()
    monkeypatch.delenv("PROFITABILITY_LEARNING_DB", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", DEPLOYED_SHA)
    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "headers", lambda prefer=None: {"authorization": "service-role"})
    monkeypatch.setattr(db, "http", fake)
    return fake


def test_exact_rejected_artifact_persists_and_is_consumed_after_replay(durable_runtime):
    from profitability_learning.acceptance import run_rejected_leadlag_acceptance

    result = run_rejected_leadlag_acceptance()

    assert result["ok"] is True
    assert result["deployed_sha"] == DEPLOYED_SHA
    assert result["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert result["screen_status"] == "PRE_OOS_FAIL"
    assert result["persistence"]["before_experiment_count"] == 0
    assert result["persistence"]["after_first_experiment_count"] == 2
    assert result["persistence"]["after_replay_experiment_count"] == 2
    assert result["persistence"]["replay_idempotent"] is True
    assert len(durable_runtime.rows) == 2
    assert result["completion"]["training"]["outcome"] == "LEARN_AND_PIVOT"
    assert result["completion"]["validation"]["outcome"] == "LEARN_AND_PIVOT"
    assert result["completion"]["training"]["persistence_status"] == "PERSISTED"
    assert result["completion"]["validation"]["persistence_status"] == "PERSISTED"

    assert result["learning_consumption"]["rejected_exact_fingerprint"] is True
    assert result["learning_consumption"]["queue_feedback_reason"] == "rejected_exact_fingerprint"
    assert result["learning_consumption"]["queue_feedback_changes_eligibility"] is True
    assert result["learning_consumption"]["heavy_dispatch_selected_count"] == 0
    assert result["learning_consumption"]["component_observation_count"] >= 1
    assert result["learning_consumption"]["mission_ids"]

    assert result["evidence_boundaries"] == {
        "candidate_returns_already_inspected": True,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
    }
    assert all(result["safety"][key] is value for key, value in SAFE.items())


def test_acceptance_rejects_resealed_substitution_and_missing_deployed_sha(
    durable_runtime, monkeypatch, tmp_path
):
    from profitability_learning.acceptance import run_rejected_leadlag_acceptance

    with gzip.open(ARTIFACT, "rt", encoding="utf-8") as handle:
        payload = copy.deepcopy(json.load(handle)["payload"])
    payload["selection"]["fingerprint_id"] = "SUBSTITUTED-v1"
    substituted = tmp_path / "substituted.json.gz"
    with gzip.open(substituted, "wt", encoding="utf-8") as handle:
        json.dump(seal_research_payload(payload), handle)

    with pytest.raises(ValueError, match="fingerprint"):
        run_rejected_leadlag_acceptance(artifact_path=substituted)
    assert durable_runtime.rows == []

    monkeypatch.delenv("RENDER_GIT_COMMIT")
    with pytest.raises(ValueError, match="deployed SHA"):
        run_rejected_leadlag_acceptance()
    assert durable_runtime.rows == []


def test_acceptance_fails_closed_if_rejected_fingerprint_enters_dispatch(
    durable_runtime, monkeypatch
):
    import profitability_learning.acceptance as acceptance

    monkeypatch.setattr(
        acceptance,
        "build_heavy_dispatch_plan",
        lambda _queue: {"selected_count": 1},
    )
    with pytest.raises(ValueError, match="admission veto"):
        acceptance.run_rejected_leadlag_acceptance()


def test_secret_protected_endpoint_accepts_no_caller_artifact(monkeypatch):
    import app
    import profitability_learning.acceptance as acceptance

    expected = {"ok": True, "deployed_sha": DEPLOYED_SHA}
    monkeypatch.setattr(app, "SCAN_SECRET", "runtime-secret")
    monkeypatch.setattr(acceptance, "run_rejected_leadlag_acceptance", lambda: expected)

    with pytest.raises(HTTPException) as exc:
        app.profitability_learning_runtime_acceptance(x_scan_secret="wrong")
    assert exc.value.status_code == 401
    assert app.profitability_learning_runtime_acceptance(
        x_scan_secret="runtime-secret"
    ) == expected

    route = next(
        route
        for route in app.app.routes
        if getattr(route, "path", None) == "/research/profitability-learning/acceptance"
    )
    assert route.methods == {"POST"}
    assert route.dependant.query_params == []
    assert [parameter.name for parameter in route.dependant.header_params] == [
        "x_scan_secret"
    ]

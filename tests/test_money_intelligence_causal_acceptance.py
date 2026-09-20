import json

import pytest
from fastapi import HTTPException

import db
from test_money_intelligence_causal_supabase import FakeSupabase


DEPLOYED_SHA = "5cf3f144820009619b5765355dc228cc05b26383"


@pytest.fixture
def durable_causal_runtime(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setenv("RENDER_GIT_COMMIT", DEPLOYED_SHA)
    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(
        db, "headers", lambda prefer=None: {"authorization": "service-role"}
    )
    monkeypatch.setattr(db, "http", fake)
    return fake


def test_acceptance_proves_support_contradiction_decay_replay_and_restart(
    durable_causal_runtime,
):
    from money_intelligence_causal_acceptance import run_causal_runtime_acceptance

    result = run_causal_runtime_acceptance()

    assert result["ok"] is True
    assert result["deployed_sha"] == DEPLOYED_SHA
    assert result["persistence"]["replay_idempotent"] is True
    assert result["persistence"]["restart_equal"] is True
    assert result["persistence"]["target_hypothesis_count"] == 2
    assert result["persistence"]["target_event_count"] == 3
    assert result["transitions"]["support_stage"]["mission_count"] == 4
    assert result["transitions"]["support_stage"]["hypothesis_ids"] == [
        "MI-RUNTIME-ACCEPT-CONTRADICTION",
        "MI-RUNTIME-ACCEPT-DECAY",
    ]
    assert result["transitions"]["contradiction_removed"] is True
    assert result["transitions"]["decay_removed"] is True
    assert result["transitions"]["current_acceptance_mission_count"] == 0
    assert result["safety"] == {
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "oos_opening_authority": False,
        "broker_connected": False,
    }
    assert len(durable_causal_runtime.rows) == 2

    replay = run_causal_runtime_acceptance()
    assert replay["persistence"]["replay_idempotent"] is True
    assert replay["persistence"]["target_state_digest_after_replay"] == result[
        "persistence"
    ]["target_state_digest_after_replay"]
    assert len(durable_causal_runtime.rows) == 2


def test_acceptance_requires_exact_deployed_sha(durable_causal_runtime, monkeypatch):
    from money_intelligence_causal_acceptance import run_causal_runtime_acceptance

    monkeypatch.delenv("RENDER_GIT_COMMIT")
    with pytest.raises(ValueError, match="deployed SHA"):
        run_causal_runtime_acceptance()
    assert durable_causal_runtime.rows == []


def test_acceptance_replays_after_unrelated_concurrent_writer(durable_causal_runtime):
    from money_intelligence_causal_acceptance import (
        _observation,
        run_causal_runtime_acceptance,
    )
    from money_intelligence_causal_supabase import SupabaseCausalMemory

    # Initialize first so the callback races the acceptance transaction rather
    # than the genesis append.
    from money_intelligence_causal_memory import CausalRepricingMemory

    SupabaseCausalMemory().initialize(CausalRepricingMemory())

    def concurrent(fake):
        memory = SupabaseCausalMemory.document_to_memory(fake.rows[-1]["payload"])
        memory.register_observation(
            _observation(
                "unrelated-concurrent-observation",
                "unrelated_metric",
                0.0,
                observed_at="2024-12-01T00:00:00Z",
                available_at="2024-12-01T01:00:00Z",
                retrieved_at="2024-12-01T02:00:00Z",
            )
        )
        fake.inject(memory.to_document())

    durable_causal_runtime.before_append = concurrent
    result = run_causal_runtime_acceptance()

    assert result["ok"] is True
    assert result["persistence"]["replay_idempotent"] is True
    restarted = SupabaseCausalMemory().load()
    assert "unrelated-concurrent-observation" in restarted.observations
    assert {"MI-RUNTIME-ACCEPT-CONTRADICTION", "MI-RUNTIME-ACCEPT-DECAY"}.issubset(
        restarted.hypotheses
    )


def test_acceptance_fails_closed_on_outage_without_sensitive_diagnostics(
    durable_causal_runtime,
):
    from money_intelligence_causal_acceptance import run_causal_runtime_acceptance

    durable_causal_runtime.available = False
    with pytest.raises(ValueError, match="causal runtime acceptance failed") as exc:
        run_causal_runtime_acceptance()
    assert "503" not in str(exc.value)


def test_secret_protected_endpoint_accepts_no_caller_payload(monkeypatch):
    import app
    import money_intelligence_causal_acceptance as acceptance

    expected = {"ok": True, "deployed_sha": DEPLOYED_SHA}
    monkeypatch.setattr(app, "SCAN_SECRET", "runtime-secret")
    monkeypatch.setattr(acceptance, "run_causal_runtime_acceptance", lambda: expected)

    with pytest.raises(HTTPException) as exc:
        app.money_intelligence_causal_runtime_acceptance(x_scan_secret="wrong")
    assert exc.value.status_code == 401
    assert app.money_intelligence_causal_runtime_acceptance(
        x_scan_secret="runtime-secret"
    ) == expected

    route = next(
        route
        for route in app.app.routes
        if getattr(route, "path", None)
        == "/research/money-intelligence/causal-acceptance"
    )
    assert route.methods == {"POST"}
    assert route.dependant.query_params == []
    assert [parameter.name for parameter in route.dependant.header_params] == [
        "x_scan_secret"
    ]


def test_endpoint_failure_is_sanitized(monkeypatch):
    import app
    import money_intelligence_causal_acceptance as acceptance

    monkeypatch.setattr(app, "SCAN_SECRET", "runtime-secret")
    monkeypatch.setattr(
        acceptance,
        "run_causal_runtime_acceptance",
        lambda: (_ for _ in ()).throw(ValueError("service-role-secret-value")),
    )

    with pytest.raises(HTTPException) as exc:
        app.money_intelligence_causal_runtime_acceptance(
            x_scan_secret="runtime-secret"
        )
    assert exc.value.status_code == 500
    assert "service-role-secret-value" not in json.dumps(exc.value.detail)

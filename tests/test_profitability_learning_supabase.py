from copy import deepcopy
from pathlib import Path

import db
import pytest

from profitability_learning.contracts import fingerprint
from profitability_learning.runtime import (
    apply_queue_feedback,
    complete_experiment,
    factory_feedback,
)
from profitability_learning.supabase_memory import SupabaseMemory
from research_experiment_factory_runner import build_heavy_dispatch_plan
from test_profitability_learning import experiment


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return deepcopy(self._payload)


class FakeSupabase:
    def __init__(self):
        self.rows = []
        self.available = True

    def get(self, url, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        return Response(payload=self.rows)

    def post(self, url, *, json, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        old = next((row for row in self.rows if row["event_id"] == json["p_event_id"]), None)
        if old is not None:
            if old["event_kind"] != json["p_event_kind"] or old["digest"] != json["p_digest"]:
                return Response(409, {"message": "immutable conflict"})
            return Response(payload=False)
        self.rows.append({
            "event_id": json["p_event_id"],
            "event_kind": json["p_event_kind"],
            "digest": json["p_digest"],
            "payload": deepcopy(json["p_payload"]),
        })
        return Response(payload=True)


@pytest.fixture
def supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.delenv("PROFITABILITY_LEARNING_DB", raising=False)
    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "headers", lambda prefer=None: {"authorization": "service-role"})
    monkeypatch.setattr(db, "http", fake)
    return fake


def test_runtime_completion_survives_restart_and_replay(supabase):
    frozen = experiment([-10, -10, -10])
    first = complete_experiment(frozen)
    assert first["persistence_status"] == "PERSISTED"
    assert first["outcome"] == "LEARN_AND_PIVOT"
    assert len(supabase.rows) == 1

    # A new adapter instance sees the same durable evidence, while exact replay
    # remains idempotent rather than fabricating another independent result.
    memory = SupabaseMemory().snapshot()
    assert [row["experiment_id"] for row in memory["experiments"]] == [first["experiment_id"]]
    assert complete_experiment(deepcopy(frozen))["input_digest"] == first["input_digest"]
    assert len(supabase.rows) == 1
    assert factory_feedback()["missions"]


def test_durable_rejection_blocks_exact_fingerprint_dispatch(supabase):
    frozen = experiment([-10, -10, -10])
    complete_experiment(frozen)
    candidate = {
        "experiment_id": "exact-repeat",
        "family": frozen["contract"]["family"],
        "strategy_fingerprint": frozen["contract"]["strategy_fingerprint"],
        "information_priority": 1.0,
        "minimum_independent_events": 1,
        "estimated_independent_events": 10,
        "eligible": True,
        "status": "READY",
    }
    queue = apply_queue_feedback({"experiments": [candidate]})
    assert queue["experiments"][0]["learning_feedback"]["reason"] == "rejected_exact_fingerprint"
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_outage_and_corrupt_event_fail_closed(supabase):
    supabase.available = False
    assert factory_feedback()["status"] == "WAIT_MEMORY_UNAVAILABLE"
    queue = apply_queue_feedback({"experiments": [{"experiment_id": "new", "information_priority": 1}],
                                  "experiment_count": 1})
    assert queue["experiments"] == []
    assert queue["experiment_count"] == 0

    supabase.available = True
    payload = complete_experiment(experiment())["contract"]
    supabase.rows[0]["digest"] = fingerprint(payload)
    assert factory_feedback()["status"] == "WAIT_MEMORY_UNAVAILABLE"


def test_transport_exception_fails_closed(supabase):
    def fail(*_args, **_kwargs):
        raise RuntimeError("network down")

    supabase.get = fail
    assert factory_feedback()["status"] == "WAIT_MEMORY_UNAVAILABLE"


def test_migration_is_private_append_only_and_bounded():
    sql = (Path(__file__).parents[1] / "supabase/migrations/20260919115951_profitability_learning_events.sql").read_text()
    required = [
        "enable row level security",
        "revoke all on table public.profitability_learning_events from public, anon, authenticated",
        "grant select, insert on table public.profitability_learning_events to service_role",
        "security invoker",
        "pg_advisory_xact_lock",
        "immutable profitability-learning event conflict",
        "profitability-learning memory full",
    ]
    assert all(fragment in sql for fragment in required)

from copy import deepcopy
from pathlib import Path

import db
import pytest

from profitability_learning.contracts import fingerprint
from profitability_learning.evolution import propose_successor
from profitability_learning.memory import Memory
from profitability_learning.runtime import (
    apply_queue_feedback,
    complete_experiment,
    factory_feedback,
)
from profitability_learning.supabase_memory import SupabaseMemory
from research_experiment_factory_runner import build_heavy_dispatch_plan
from test_profitability_learning import experiment
from test_profitability_learning_memory import later, successor_contract


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
        self.before_append = None
        self.append_attempts = 0
        self.force_stale = False

    def get(self, url, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        return Response(payload=self.rows)

    def post(self, url, *, json, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        self.append_attempts += 1
        old = next((row for row in self.rows if row["event_id"] == json["p_event_id"]), None)
        if old is not None:
            if old["event_kind"] != json["p_event_kind"] or old["digest"] != json["p_digest"]:
                return Response(409, {"message": "immutable conflict"})
            return Response(payload="EXISTS")
        if self.before_append is not None:
            callback, self.before_append = self.before_append, None
            callback(self)
        actual_sequence = self.rows[-1]["sequence"] if self.rows else 0
        if self.force_stale:
            return Response(payload="STALE")
        if (json["p_expected_count"], json["p_expected_sequence"]) != (len(self.rows), actual_sequence):
            return Response(payload="STALE")
        self.rows.append({
            "sequence": actual_sequence + 1,
            "event_id": json["p_event_id"],
            "event_kind": json["p_event_kind"],
            "digest": json["p_digest"],
            "payload": deepcopy(json["p_payload"]),
        })
        return Response(payload="APPENDED")

    def inject_experiment(self, payload):
        self.rows.append({
            "sequence": self.rows[-1]["sequence"] + 1 if self.rows else 1,
            "event_id": payload["experiment_id"],
            "event_kind": "experiment",
            "digest": fingerprint(payload),
            "payload": deepcopy(payload),
        })


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


def test_stale_completion_is_reclassified_against_concurrent_evidence(supabase, tmp_path):
    frozen = experiment([-10, -10, -10])
    frozen["contract"]["mechanism_falsifier"] = {
        "metric": "after_cost_expectancy_money",
        "maximum": 0,
        "minimum_independent_replications": 2,
    }
    complete_experiment(frozen)

    # Prepare the immutable result another worker commits after this worker's
    # read but before its append. The retry must classify against that evidence.
    local = Memory(tmp_path / "concurrent.sqlite")
    local.complete(frozen)
    concurrent = local.complete(later(frozen, 60))
    supabase.before_append = lambda fake: fake.inject_experiment(concurrent)

    result = complete_experiment(later(frozen, 30))
    assert result["outcome"] == "MECHANISM_DEAD"
    assert supabase.append_attempts == 3  # initial seed, stale append, successful retry


def test_repeated_stale_writes_fail_closed_after_bounded_retries(supabase):
    supabase.force_stale = True
    with pytest.raises(ValueError, match="changed during completion"):
        complete_experiment(experiment())
    assert supabase.append_attempts == 3
    assert supabase.rows == []


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


def test_archive_proposal_identity_is_validated_before_any_remote_append(supabase, tmp_path):
    source = Memory(tmp_path / "source.sqlite")
    parent = experiment([-10, -10, -10])
    completed = source.complete(parent)
    proposal = propose_successor(
        source.snapshot(),
        completed["experiment_id"],
        successor_contract(parent),
        economic_reason="Fresh exit mechanism with fixed predeclared evidence.",
        falsifier="Reject when fresh after-cost replication is non-positive.",
    )
    source.save_proposal(proposal)
    valid_archive = source.export()
    forged_archive = deepcopy(valid_archive)
    proposal_event = next(
        row for row in forged_archive["events"] if row["kind"] == "proposal"
    )
    proposal_event["payload"]["ancestry"]["failure_lesson"] = "SUCCESS_LEARN"
    proposal_event["digest"] = fingerprint(proposal_event["payload"])
    forged_archive["sha256"] = fingerprint(forged_archive["events"])

    with pytest.raises(ValueError, match="proposal identity"):
        SupabaseMemory().import_archive(forged_archive)

    assert supabase.rows == []
    SupabaseMemory().import_archive(valid_archive)
    SupabaseMemory().import_archive(valid_archive)
    assert len(supabase.rows) == 2
    assert SupabaseMemory().snapshot()["proposals"] == [proposal]

    followup = later(experiment([-10, -10, -10]), 60)
    followup["contract"] = successor_contract(parent)
    source.complete(followup)
    archive_with_successor = source.export()
    SupabaseMemory().import_archive(archive_with_successor)
    SupabaseMemory().import_archive(archive_with_successor)
    assert len(supabase.rows) == 3


def test_migration_is_private_append_only_and_bounded():
    migrations = Path(__file__).parents[1] / "supabase/migrations"
    sql = "\n".join(path.read_text() for path in sorted(migrations.glob("*profitability_learning*.sql")))
    required = [
        "enable row level security",
        "revoke all on table public.profitability_learning_events from public, anon, authenticated",
        "grant select, insert on table public.profitability_learning_events to service_role",
        "security invoker",
        "pg_advisory_xact_lock",
        "immutable profitability-learning event conflict",
        "profitability-learning memory full",
        "append_profitability_learning_event_v2",
        "p_expected_count",
        "p_expected_sequence",
        "profitability_learning_events:append:v2",
        "return 'STALE'",
    ]
    assert all(fragment in sql for fragment in required)

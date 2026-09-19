from copy import deepcopy
from pathlib import Path

import db
import pytest

from money_intelligence_causal_memory import (
    CausalMemoryError,
    EvidenceEvent,
    FrozenHypothesis,
    ReplayConflictError,
)
from money_intelligence_causal_supabase import SupabaseCausalMemory
from test_money_intelligence_causal_memory import (
    _hypothesis,
    _memory_with_hypothesis,
    _observation,
    _support,
)


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
        self.force_stale = False
        self.append_attempts = 0

    def get(self, _url, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        return Response(payload=list(reversed(self.rows[-2:])))

    def post(self, _url, *, json, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        self.append_attempts += 1
        existing = next(
            (
                row
                for row in self.rows
                if row["content_digest"] == json["p_content_digest"]
            ),
            None,
        )
        if existing is not None:
            if (
                existing["parent_digest"] != json["p_parent_digest"]
                or existing["payload"] != json["p_payload"]
            ):
                return Response(409, {"message": "immutable conflict"})
            return Response(payload="EXISTS")
        if self.before_append is not None:
            callback, self.before_append = self.before_append, None
            callback(self)
        latest = self.rows[-1] if self.rows else None
        actual_sequence = latest["sequence"] if latest else 0
        actual_digest = latest["content_digest"] if latest else None
        if self.force_stale or (
            json["p_expected_sequence"], json["p_expected_digest"]
        ) != (actual_sequence, actual_digest):
            return Response(payload="STALE")
        self.rows.append(
            {
                "sequence": actual_sequence + 1,
                "content_digest": json["p_content_digest"],
                "parent_digest": json["p_parent_digest"],
                "payload": deepcopy(json["p_payload"]),
            }
        )
        return Response(payload="APPENDED")

    def inject(self, document):
        latest = self.rows[-1] if self.rows else None
        self.rows.append(
            {
                "sequence": (latest["sequence"] if latest else 0) + 1,
                "content_digest": document["content_digest"],
                "parent_digest": latest["content_digest"] if latest else None,
                "payload": deepcopy(document),
            }
        )


@pytest.fixture
def supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "headers", lambda prefer=None: {"authorization": "service-role"})
    monkeypatch.setattr(db, "http", fake)
    return fake


def _contradiction(event_id="contradiction-1"):
    return EvidenceEvent(
        event_id=event_id,
        hypothesis_id="H1",
        evaluated_at="2026-09-04T00:00:00Z",
        kind="contradiction",
        matched_controls=("market_beta", "volatility_regime"),
        outcome_observation_ids=("adverse-outcome",),
        control_observation_ids=("control",),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=40,
        confirmatory=True,
        p_value=0.01,
    )


def test_durable_restart_preserves_scientific_state_and_behavior(supabase):
    memory = _memory_with_hypothesis(half_life_days=30.0)
    memory.record_evidence(_support())
    original = deepcopy(memory.to_document())

    first = SupabaseCausalMemory()
    assert first.initialize(memory) == "APPENDED"

    restarted = SupabaseCausalMemory().load()
    assert restarted.to_document() == original
    gained = restarted.confidence("H1", as_of="2026-09-03T00:00:00Z")
    decayed = restarted.confidence("H1", as_of="2026-12-03T00:00:00Z")
    assert gained.score > decayed.score > 0.5
    assert restarted.hypotheses["H1"].family_size == 2
    assert restarted.observations["flow"].provenance_uri == "source://fixture"

    adapter = SupabaseCausalMemory()
    adapter.transact(lambda current: current.record_evidence(_contradiction()))
    weakened = SupabaseCausalMemory().load()
    assert weakened.confidence("H1", as_of="2026-09-04T00:00:00Z").score < 0.5
    assert [event.event_id for event in weakened.contradiction_ledger()] == [
        "contradiction-1"
    ]

    adapter.transact(lambda current: current.reject_hypothesis("H1"))
    rejected = SupabaseCausalMemory().load()
    replacement = FrozenHypothesis(
        **{**_hypothesis().__dict__, "hypothesis_id": "H2"}
    )
    with pytest.raises(CausalMemoryError, match="rejected"):
        rejected.register_hypothesis(replacement)
    assert rejected.research_artifact(
        "H1", lane="big_move", as_of="2026-09-04T00:00:00Z"
    ) is None


def test_stale_writer_replays_mutation_against_fresh_durable_state(supabase):
    SupabaseCausalMemory().initialize(_memory_with_hypothesis())

    def concurrent(fake):
        memory = SupabaseCausalMemory.document_to_memory(fake.rows[-1]["payload"])
        memory.register_observation(_observation("concurrent"))
        fake.inject(memory.to_document())

    supabase.before_append = concurrent
    own = _observation("own")
    SupabaseCausalMemory().transact(lambda memory: memory.register_observation(own))

    restarted = SupabaseCausalMemory().load()
    assert {"concurrent", "own"}.issubset(restarted.observations)
    assert supabase.append_attempts == 3  # initialize, stale write, successful retry


def test_outage_corruption_missing_state_and_repeated_stale_fail_closed(supabase):
    with pytest.raises(CausalMemoryError, match="not initialized"):
        SupabaseCausalMemory().load()

    SupabaseCausalMemory().initialize(_memory_with_hypothesis())
    supabase.available = False
    with pytest.raises(CausalMemoryError, match="read failed"):
        SupabaseCausalMemory().load()

    supabase.available = True
    supabase.rows[-1]["payload"]["half_life_days"] = 999
    with pytest.raises(CausalMemoryError, match="integrity"):
        SupabaseCausalMemory().load()

    supabase.rows.clear()
    SupabaseCausalMemory().initialize(_memory_with_hypothesis())
    original_post = supabase.post
    supabase.post = lambda *_args, **_kwargs: Response(503, {"message": "outage"})
    with pytest.raises(CausalMemoryError, match="append failed"):
        SupabaseCausalMemory().transact(
            lambda memory: memory.register_observation(_observation("not-durable"))
        )
    supabase.post = original_post

    supabase.force_stale = True
    with pytest.raises(CausalMemoryError, match="changed during transaction"):
        SupabaseCausalMemory().transact(
            lambda memory: memory.register_observation(_observation("never-written"))
        )
    assert "never-written" not in SupabaseCausalMemory().load().observations


def test_conflicting_replay_remains_rejected_after_backend_restart(supabase):
    SupabaseCausalMemory().initialize(_memory_with_hypothesis())
    conflicting = _observation("flow", value=999.0)
    with pytest.raises(ReplayConflictError, match="different content"):
        SupabaseCausalMemory().transact(
            lambda memory: memory.register_observation(conflicting)
        )
    assert len(supabase.rows) == 1


def test_migration_is_private_append_only_digest_bound_and_optimistic():
    migrations = Path(__file__).parents[1] / "supabase/migrations"
    sql = "\n".join(
        path.read_text()
        for path in sorted(migrations.glob("*money_intelligence_causal_memory*.sql"))
    )
    required = [
        "enable row level security",
        "revoke all on table public.money_intelligence_causal_memory_versions from public, anon, authenticated",
        "authenticated, service_role",
        "grant select, insert on table public.money_intelligence_causal_memory_versions to service_role",
        "security invoker",
        "pg_advisory_xact_lock",
        "immutable causal-memory version conflict",
        "causal-memory version store full",
        "append_money_intelligence_causal_memory_version_v1",
        "p_expected_sequence",
        "p_expected_digest",
        "p_parent_digest",
        "money_intelligence_causal_memory_versions:append:v1",
        "return 'STALE'",
    ]
    assert all(fragment in sql for fragment in required)

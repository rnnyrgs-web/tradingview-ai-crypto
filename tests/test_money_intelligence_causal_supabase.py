from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import db
import pytest

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EvidenceEvent,
    FrozenHypothesis,
    ReplayConflictError,
)
from money_intelligence_causal_supabase import SupabaseCausalMemory
from test_money_intelligence_causal_memory import (
    _clone_evidence_units,
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
        self.server_time = "2026-09-02T00:30:00Z"
        self.available = True
        self.before_append = None
        self.force_stale = False
        self.append_attempts = 0

    def get(self, _url, **_kwargs):
        if not self.available:
            return Response(503, {"message": "unavailable"})
        params = _kwargs.get("params", {})
        if params.get("order") == "sequence.asc":
            import json as json_module

            hypothesis_id = json_module.loads(params["payload"][3:])["hypotheses"][0]["hypothesis_id"]
            matches = [
                row for row in self.rows
                if any(
                    hypothesis["hypothesis_id"] == hypothesis_id
                    for hypothesis in row["payload"]["hypotheses"]
                )
            ]
            return Response(payload=matches[:1])
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
                "created_at": self.server_time,
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
                "created_at": self.server_time,
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
        control_observation_ids=("adverse-control",),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=1,
        confirmatory=True,
        p_value=None,
    )


def _plan_only():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))
    memory.register_hypothesis(_hypothesis())
    return memory


def _append_evaluation_observations(current, prepared):
    for observation in prepared.observations.values():
        if observation.observation_id not in current.observations:
            current.register_observation(observation)


def test_plan_and_outcomes_cannot_first_arrive_in_one_durable_version(supabase):
    prepared = _memory_with_hypothesis()
    with pytest.raises(CausalMemoryError, match="durable before outcome"):
        SupabaseCausalMemory().initialize(prepared)
    assert supabase.rows == []

    adapter = SupabaseCausalMemory()
    adapter.initialize(CausalRepricingMemory())

    def one_step(current):
        current.register_observation(_observation("flow"))
        current.register_hypothesis(_hypothesis())
        _append_evaluation_observations(current, prepared)
        current.record_evidence(_support())

    with pytest.raises(CausalMemoryError, match="durable before outcome"):
        adapter.transact(one_step)
    assert len(supabase.rows) == 1

    adapter.transact(
        lambda current: (
            current.register_observation(_observation("flow")),
            current.register_hypothesis(_hypothesis()),
        )
    )
    adapter.transact(
        lambda current: (
            _append_evaluation_observations(current, prepared),
            current.record_evidence(_support()),
        )
    )
    assert adapter.load().confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 1


def test_backdated_plan_cannot_confirm_outcomes_that_started_before_server_commit(supabase):
    supabase.server_time = "2026-09-03T00:00:00Z"
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())
    prepared = _memory_with_hypothesis()

    with pytest.raises(CausalMemoryError, match="server-recorded plan commit"):
        adapter.transact(lambda current: _append_evaluation_observations(current, prepared))
    assert len(supabase.rows) == 1


def test_original_plan_receipt_survives_unrelated_later_version(supabase):
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())
    supabase.server_time = "2026-09-03T00:00:00Z"
    adapter.transact(
        lambda current: current.register_observation(
            _observation("unrelated", subject_id="ETH-USD")
        )
    )
    prepared = _memory_with_hypothesis()
    adapter.transact(
        lambda current: (
            _append_evaluation_observations(current, prepared),
            current.record_evidence(_support()),
        )
    )
    assert adapter.load().confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 1


def test_rejected_fingerprints_cannot_be_removed_from_durable_history(supabase):
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())
    adapter.transact(lambda current: current.reject_hypothesis("H1"))
    original = set(adapter.load().rejected_fingerprints)

    with pytest.raises(CausalMemoryError, match="durable causal-memory history is immutable"):
        adapter.transact(lambda current: current.rejected_fingerprints.clear())
    assert adapter.load().rejected_fingerprints == original


def test_durable_restart_preserves_scientific_state_and_behavior(supabase):
    memory = _memory_with_hypothesis(half_life_days=30.0)
    memory.record_evidence(_support())

    first = SupabaseCausalMemory()
    assert first.initialize(_plan_only()) == "APPENDED"
    def seed(current):
        _append_evaluation_observations(current, memory)
        current.record_evidence(_support())
    first.transact(seed)
    original = deepcopy(SupabaseCausalMemory().load().to_document())

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
    SupabaseCausalMemory().initialize(_plan_only())

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


def test_stale_writer_cannot_reconsume_units_after_concurrent_confirmatory_write(supabase):
    memory = _memory_with_hypothesis()
    original = _support("concurrent-confirmatory")
    clone = _clone_evidence_units(
        memory,
        original,
        suffix="stale-writer-clone",
        observation_changes={"currency": "bp", "unit": "bp", "venue": "other"},
        value_scale=10_000.0,
    )
    clone = replace(clone, confirmatory=False, p_value=None)
    SupabaseCausalMemory().initialize(_plan_only())
    SupabaseCausalMemory().transact(
        lambda current: _append_evaluation_observations(current, memory)
    )

    def concurrent(fake):
        current = SupabaseCausalMemory.document_to_memory(fake.rows[-1]["payload"])
        assert current.record_evidence(original)
        fake.inject(current.to_document())

    supabase.before_append = concurrent
    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        SupabaseCausalMemory().transact(
            lambda current: current.record_evidence(clone)
        )

    restarted = SupabaseCausalMemory().load()
    assert set(restarted.events) == {original.event_id}
    assert restarted.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 1


def test_durable_control_substitution_cannot_create_confirmatory_support(supabase):
    prepared = _memory_with_hypothesis()
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())
    replacement_ids = tuple(f"durable-posthoc-control-{index}" for index in range(1, 7))

    def seed_observations(current):
        _append_evaluation_observations(current, prepared)
        for replacement_id, source_id in zip(
            replacement_ids,
            _support().control_observation_ids,
            strict=True,
        ):
            current.register_observation(
                replace(
                    prepared.observations[source_id],
                    observation_id=replacement_id,
                    value=-1.0,
                )
            )

    adapter.transact(seed_observations)
    attack = replace(
        _support("durable-posthoc-control-substitution"),
        control_observation_ids=replacement_ids,
    )

    with pytest.raises(CausalMemoryError, match="frozen outcome/control pairs"):
        adapter.transact(lambda current: current.record_evidence(attack))

    restarted = SupabaseCausalMemory().load()
    assert "durable-posthoc-control-substitution" not in restarted.events
    assert restarted.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0


def test_durable_planned_control_ids_cannot_hide_substituted_provenance(supabase):
    prepared = _memory_with_hypothesis()
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())

    def seed_substituted_controls(current):
        for outcome_id, control_id in prepared.hypotheses["H1"].evaluation_pairs:
            current.register_observation(prepared.observations[outcome_id])
            current.register_observation(
                replace(
                    prepared.observations[control_id],
                    metric_name="posthoc_selected_control",
                    source_id="posthoc-selected-provider",
                    provenance_uri=f"posthoc://{control_id}",
                )
            )

    adapter.transact(seed_substituted_controls)
    with pytest.raises(CausalMemoryError, match="frozen control provenance"):
        adapter.transact(
            lambda current: current.record_evidence(
                _support("durable-planned-id-control-substitution")
            )
        )

    restarted = adapter.load()
    assert "durable-planned-id-control-substitution" not in restarted.events
    assert restarted.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0


def test_outage_corruption_missing_state_and_repeated_stale_fail_closed(supabase):
    with pytest.raises(CausalMemoryError, match="not initialized"):
        SupabaseCausalMemory().load()

    SupabaseCausalMemory().initialize(_plan_only())
    supabase.available = False
    with pytest.raises(CausalMemoryError, match="read failed"):
        SupabaseCausalMemory().load()

    supabase.available = True
    supabase.rows[-1]["payload"]["half_life_days"] = 999
    with pytest.raises(CausalMemoryError, match="integrity"):
        SupabaseCausalMemory().load()

    supabase.rows.clear()
    SupabaseCausalMemory().initialize(_plan_only())
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
    SupabaseCausalMemory().initialize(_plan_only())
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
    server_time_migration = (
        migrations / "20260920080642_causal_memory_server_time_insert_privileges.sql"
    ).read_text()
    assert "revoke insert on table public.money_intelligence_causal_memory_versions" in server_time_migration
    assert "grant insert (content_digest, parent_digest, payload)" in server_time_migration
    assert "grant insert (content_digest, parent_digest, payload, created_at)" not in server_time_migration
    assert "alter column created_at set default clock_timestamp()" in server_time_migration

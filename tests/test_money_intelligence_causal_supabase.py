from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import db
import pytest
import money_intelligence_causal_acceptance as acceptance
import money_intelligence_causal_memory as causal_memory

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

_PRODUCTION_SUPPORT_ATTESTATION = causal_memory._trusted_support_attestation


@pytest.fixture(autouse=True)
def _test_source_receipt(monkeypatch):
    """The durable-adapter fixtures simulate an external test-source receipt."""
    production_verify = causal_memory._trusted_control_selection

    def verify(hypothesis, contract, outcome, control):
        if (
            contract.control_selection_contract_id == "market-beta-volatility-v1"
            and outcome.source_id == control.source_id == "test-source"
        ):
            return True
        return production_verify(hypothesis, contract, outcome, control)

    monkeypatch.setattr(causal_memory, "_trusted_control_selection", verify)
    monkeypatch.setattr(causal_memory, "_trusted_support_attestation", lambda memory, hypothesis, event: True)


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
        if "payload->>authority_attestation" in params:
            matches = [
                row for row in reversed(self.rows)
                if "authority_attestation" in row["payload"]
            ]
            return Response(payload=deepcopy(matches[:1]))
        if params.get("order") == "sequence.asc" and "payload" in params:
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
        if params.get("order") == "sequence.asc":
            return Response(payload=deepcopy(self.rows))
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


def test_raw_appended_version_cannot_roll_back_rejected_state(supabase):
    prepared = _memory_with_hypothesis()
    adapter = SupabaseCausalMemory()
    adapter.initialize(_plan_only())
    adapter.transact(
        lambda current: (
            _append_evaluation_observations(current, prepared),
            current.record_evidence(_support()),
        )
    )
    adapter.transact(lambda current: current.reject_hypothesis("H1"))

    attacked = adapter.load().to_document()
    attacked["rejected_fingerprints"] = []
    attacked.pop("content_digest")
    attacked["content_digest"] = causal_memory._sha256(attacked)
    supabase.inject(attacked)

    with pytest.raises(CausalMemoryError, match="durable causal-memory history is immutable"):
        adapter.load()


def test_second_raw_append_cannot_launder_acceptance_state_rollback(
    supabase, monkeypatch
):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)
    ids = acceptance._ids("f" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    plan = CausalRepricingMemory()
    acceptance._freeze_support_contract(plan, ids, base)
    adapter = SupabaseCausalMemory()
    supabase.server_time = "2026-09-20T00:30:00Z"
    adapter.initialize(plan)
    adapter.transact(lambda current: acceptance._seed_support(current, ids, base))
    adapter.transact(lambda current: current.reject_hypothesis(ids["hypothesis"]))

    rollback = adapter.load().to_document()
    rollback["rejected_fingerprints"] = []
    rollback["half_life_days"] = 999.0
    rollback.pop("content_digest")
    rollback["content_digest"] = causal_memory._sha256(rollback)
    supabase.inject(rollback)

    cover = deepcopy(rollback)
    cover["attacker_nonce"] = "second-raw-version"
    cover.pop("content_digest")
    cover["content_digest"] = causal_memory._sha256(cover)
    supabase.inject(cover)

    with pytest.raises(CausalMemoryError, match="authenticated durable causal-memory"):
        adapter.load()


def test_legacy_unsigned_acceptance_state_is_quarantined_then_resigned(
    supabase, monkeypatch
):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)
    monkeypatch.setattr(
        causal_memory,
        "_trusted_support_attestation",
        _PRODUCTION_SUPPORT_ATTESTATION,
    )
    ids = acceptance._ids("1" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    legacy = CausalRepricingMemory()
    acceptance._seed_support(legacy, ids, base)
    document = legacy.to_document()
    document.pop("authority_attestation")
    support = next(
        row for row in document["events"] if row["event_id"] == ids["support"]
    )
    support["note"] = "causal-acceptance-support-v1:" + "0" * 64
    document.pop("content_digest")
    document["content_digest"] = causal_memory._sha256(document)
    supabase.inject(document)

    adapter = SupabaseCausalMemory()
    restored = adapter.load()
    assert restored.events[ids["support"]].confirmatory is False
    adapter.transact(
        lambda current: current.register_observation(
            replace(
                acceptance._observation(
                    "legacy-migration-marker",
                    metric_name="migration_marker",
                    value=1.0,
                    observed_at=base,
                    available_at=base,
                    unit="count",
                    window_hours=1,
                ),
                subject_id="LEGACY-MIGRATION",
            )
        )
    )
    assert supabase.rows[-1]["payload"]["authority_attestation"].startswith(
        "causal-memory-document-v1:"
    )
    assert adapter.load().events[ids["support"]].confirmatory is False


def test_marker_free_cover_cannot_launder_legacy_unsigned_rollback(
    supabase, monkeypatch
):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)
    ids = acceptance._ids("4" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    legacy = CausalRepricingMemory()
    acceptance._seed_support(legacy, ids, base)
    legacy.reject_hypothesis(ids["hypothesis"])
    event = legacy.events[ids["support"]]
    legacy.events[ids["support"]] = replace(
        event,
        note="causal-acceptance-support-v1:" + "0" * 64,
        confirmatory=False,
    )
    unsigned_v1 = legacy.to_document()
    unsigned_v1.pop("authority_attestation", None)
    unsigned_v1.pop("content_digest")
    unsigned_v1["content_digest"] = causal_memory._sha256(unsigned_v1)
    supabase.inject(unsigned_v1)
    monkeypatch.delenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY")

    rollback = deepcopy(unsigned_v1)
    rollback["events"] = []
    rollback["event_order"] = []
    rollback["registration_log"] = [
        row for row in rollback["registration_log"] if row["kind"] != "event"
    ]
    rollback["rejected_fingerprints"] = []
    rollback["half_life_days"] = 999.0
    rollback.pop("content_digest")
    rollback["content_digest"] = causal_memory._sha256(rollback)
    supabase.inject(rollback)

    cover = deepcopy(rollback)
    cover["attacker_nonce"] = "marker-free-cover"
    cover.pop("content_digest")
    cover["content_digest"] = causal_memory._sha256(cover)
    supabase.inject(cover)

    adapter = SupabaseCausalMemory()
    with pytest.raises(
        CausalMemoryError, match="durable causal-memory history is immutable"
    ):
        adapter.load()
    with pytest.raises(
        CausalMemoryError, match="durable causal-memory history is immutable"
    ):
        adapter.transact(
            lambda current: current.register_observation(
                _observation("trusted-mutation-after-cover")
            )
        )


def test_document_attestation_cannot_be_removed_after_legacy_migration(
    supabase, monkeypatch
):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)
    ids = acceptance._ids("2" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    memory = CausalRepricingMemory()
    acceptance._seed_support(memory, ids, base)
    event = memory.events[ids["support"]]
    memory.events[ids["support"]] = replace(
        event,
        note="causal-acceptance-support-v1:" + "0" * 64,
        confirmatory=False,
    )
    signed = memory.to_document()
    supabase.inject(signed)

    stripped = deepcopy(signed)
    stripped.pop("authority_attestation")
    stripped.pop("content_digest")
    stripped["content_digest"] = causal_memory._sha256(stripped)
    supabase.inject(stripped)

    with pytest.raises(CausalMemoryError, match="attested boundary cannot be removed"):
        SupabaseCausalMemory().load()


def test_acceptance_markers_cannot_be_removed_after_attested_boundary(
    supabase, monkeypatch
):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)
    ids = acceptance._ids("3" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    memory = CausalRepricingMemory()
    acceptance._seed_support(memory, ids, base)
    memory.reject_hypothesis(ids["hypothesis"])
    signed = memory.to_document()
    supabase.inject(signed)

    removed = deepcopy(signed)
    removed.pop("authority_attestation")
    removed["events"] = []
    removed["event_order"] = []
    removed["registration_log"] = [
        row for row in removed["registration_log"] if row["kind"] != "event"
    ]
    removed["rejected_fingerprints"] = []
    removed["half_life_days"] = 999.0
    removed.pop("content_digest")
    removed["content_digest"] = causal_memory._sha256(removed)
    supabase.inject(removed)

    cover = deepcopy(removed)
    cover["attacker_nonce"] = "marker-removal-cover"
    cover.pop("content_digest")
    cover["content_digest"] = causal_memory._sha256(cover)
    supabase.inject(cover)

    with pytest.raises(CausalMemoryError, match="attested boundary cannot be removed"):
        SupabaseCausalMemory().load()


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

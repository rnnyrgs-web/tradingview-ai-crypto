from copy import deepcopy
from pathlib import Path

import pytest

import db
from money_intelligence_learning.contracts import freeze_mechanism, make_evidence
from money_intelligence_learning.supabase_memory import SupabaseMemory


def contract():
    return freeze_mechanism(
        {
            "schema_version": 1,
            "mechanism_key": "spot-led-retention-after-squeeze",
            "claim": "Price retention after forced flow normalizes may indicate independent spot demand.",
            "causal_chain": ["forced flow ends", "price retains", "spot demand persists", "repricing continues"],
            "expected_direction": "POSITIVE",
            "expected_horizon_days": 30,
            "falsifier": "Retention disappears in matched non-spot controls.",
            "transmission_variables": ["liquidations", "open_interest", "spot_volume"],
            "matched_control_design": {
                "control_group": "large moves without post-squeeze retention",
                "matching_variables": ["shock_size", "market_beta"],
                "failure_condition": "treated returns do not exceed controls",
            },
            "regime_scope": ["liquid_crypto"],
            "frozen_at": "2026-01-01T00:00:00+00:00",
            "information_cutoff": "2026-01-01T00:00:00+00:00",
            "prior_confidence": 0.3,
            "decay_half_life_days": 14,
            "minimum_supporting_sources": 1,
            "minimum_matched_controls": 0,
            "search_breadth": 1,
            "target_assets": ["BTC"],
            "downstream_lanes": ["BIG_MOVE"],
        }
    )


def observation(frozen):
    return make_evidence(
        frozen,
        {
            "schema_version": 1,
            "evidence_kind": "SUPPORT",
            "observed_at": "2026-01-02T00:00:00+00:00",
            "published_at": "2026-01-02T00:01:00+00:00",
            "available_at": "2026-01-02T00:02:00+00:00",
            "information_cutoff": "2026-01-02T00:02:00+00:00",
            "source": {"publisher": "exchange", "uri": "https://example.test/exchange", "source_type": "OFFICIAL_DATA"},
            "independence_key": "btc-squeeze-2026-01-02",
            "strength": 0.8,
            "structured_fact": {"retained_return": 0.04, "liquidations_normalized": True},
            "matched_control": None,
            "narrative_summary": "Research observation only.",
        },
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
        self.force_stale = 0
        self.append_attempts = 0

    def get(self, url, *, headers, params):
        if not self.available:
            return Response(503, {"error": "down"})
        return Response(payload=self.rows)

    def post(self, url, *, headers, json):
        self.append_attempts += 1
        if not self.available:
            return Response(503, {"error": "down"})
        if self.force_stale:
            self.force_stale -= 1
            return Response(payload="STALE")
        existing = next((row for row in self.rows if row["event_id"] == json["p_event_id"]), None)
        if existing:
            if existing["event_kind"] != json["p_event_kind"] or existing["digest"] != json["p_digest"]:
                return Response(409, {"error": "immutable conflict"})
            return Response(payload="EXISTS")
        count = len(self.rows)
        sequence = self.rows[-1]["sequence"] if self.rows else 0
        if count != json["p_expected_count"] or sequence != json["p_expected_sequence"]:
            return Response(payload="STALE")
        self.rows.append(
            {
                "sequence": sequence + 1,
                "event_id": json["p_event_id"],
                "event_kind": json["p_event_kind"],
                "digest": json["p_digest"],
                "payload": deepcopy(json["p_payload"]),
            }
        )
        return Response(payload="APPENDED")


@pytest.fixture
def supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(db, "headers", lambda prefer=None: {"authorization": "service-role"})
    monkeypatch.setattr(db, "http", fake)
    return fake


def test_supabase_memory_survives_restart_and_exact_replay(supabase):
    frozen = contract()
    item = observation(frozen)
    first = SupabaseMemory()
    first.freeze(frozen)
    first.append_evidence(item)
    SupabaseMemory().freeze(deepcopy(frozen))
    SupabaseMemory().append_evidence(deepcopy(item))

    snapshot = SupabaseMemory().snapshot(as_of="2026-01-02T00:02:00+00:00")
    assert len(supabase.rows) == 2
    assert len(snapshot["evidence"]) == 1
    assert snapshot["mechanisms"][frozen["mechanism_id"]]["state"]["status"] == "PROMISING"


def test_supabase_memory_retries_stale_compare_and_swap(supabase):
    frozen = contract()
    memory = SupabaseMemory()
    memory.freeze(frozen)
    supabase.force_stale = 1
    memory.append_evidence(observation(frozen))
    assert len(supabase.rows) == 2
    assert supabase.append_attempts == 3


def test_supabase_memory_fails_closed_on_repeated_stale_outage_or_corruption(supabase):
    frozen = contract()
    memory = SupabaseMemory()
    memory.freeze(frozen)
    supabase.force_stale = 3
    with pytest.raises(ValueError, match="changed during append"):
        memory.append_evidence(observation(frozen))

    supabase.force_stale = 0
    supabase.available = False
    with pytest.raises(ValueError, match="read failed"):
        memory.snapshot(as_of="2026-01-02T00:02:00+00:00")

    supabase.available = True
    supabase.rows[0]["digest"] = "0" * 64
    with pytest.raises(ValueError, match="integrity"):
        memory.snapshot(as_of="2026-01-02T00:02:00+00:00")


def test_money_intelligence_migration_is_private_append_only_and_bounded():
    migrations = Path(__file__).parents[1] / "supabase/migrations"
    sql = "\n".join(path.read_text() for path in sorted(migrations.glob("*money_intelligence_learning*.sql")))
    required = [
        "enable row level security",
        "revoke all on table public.money_intelligence_learning_events from public, anon, authenticated",
        "grant select, insert on table public.money_intelligence_learning_events to service_role",
        "security invoker",
        "pg_advisory_xact_lock",
        "immutable money-intelligence event conflict",
        "money-intelligence memory full",
        "append_money_intelligence_learning_event",
        "p_expected_count",
        "p_expected_sequence",
        "return 'STALE'",
    ]
    assert all(fragment in sql for fragment in required)

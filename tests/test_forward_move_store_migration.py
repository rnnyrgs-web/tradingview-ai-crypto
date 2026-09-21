from pathlib import Path


def _sql():
    root = Path(__file__).parents[1]
    return (
        root
        / "supabase/migrations/20260921051500_big_move_forward_formations.sql"
    ).read_text(encoding="utf-8")


def test_reference_observation_store_is_append_only_and_server_timed():
    sql = _sql()
    lowered = sql.lower()

    assert "create table if not exists public.big_move_reference_observations" in sql
    assert "created_at timestamptz not null default clock_timestamp()" in sql
    assert "append_big_move_reference_observation_v1" in sql
    assert "captured_at >= created_at - interval '5 minutes'" in sql
    assert "grant select on table public.big_move_reference_observations to service_role" in sql
    assert "grant insert" not in "\n".join(
        line for line in lowered.splitlines()
        if "big_move_reference_observations" in line and "grant insert" in line
    )
    assert "update public.big_move_reference_observations" not in lowered
    assert "delete from public.big_move_reference_observations" not in lowered


def test_forward_formation_store_rejects_stale_backdated_payloads():
    sql = _sql()

    assert "formation_payload ? 'formed_at'" in sql
    assert "formation_payload ? 'evidence_cutoff'" in sql
    assert "formation_payload ? 'reference_price_observed_at'" in sql
    assert "created_at - interval '5 minutes'" in sql
    assert "(formation_payload ->> 'formed_at')::timestamptz <= created_at" in sql
    assert "(formation_payload ->> 'reference_price_observed_at')::timestamptz <= created_at" in sql
    assert "update public.big_move_forward_formations" not in sql.lower()
    assert "delete from public.big_move_forward_formations" not in sql.lower()


def test_formation_rpc_must_consume_and_match_durable_reference_receipt():
    sql = _sql()
    lowered = sql.lower()

    assert "reference_observation_sequence bigint not null" in sql
    assert "references public.big_move_reference_observations(sequence)" in sql
    assert "p_reference_observation_sequence bigint" in sql
    assert "missing durable big-move reference observation" in sql
    assert "formation does not match durable big-move reference observation" in sql
    assert "'big_move_reference:' || ref.sequence::text" in sql
    assert "p_formation_payload ->> 'reference_price_observation_sha256'" in sql
    assert "p_formation_payload ->> 'reference_price_source_id'" in sql
    assert "p_formation_payload ->> 'reference_price_observed_at'" in sql
    assert "p_formation_payload ->> 'reference_price'" in sql
    assert "grant insert (forecast_fingerprint, formation_payload)" not in sql
    assert "security definer" in lowered


def test_sql_explicitly_does_not_claim_provider_origin_authentication():
    sql = _sql().lower()
    assert "does not by" in sql
    assert "provider-origin authentication remains a separate required service-boundary gate" in sql

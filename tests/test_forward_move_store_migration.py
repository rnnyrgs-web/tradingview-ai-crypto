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


def test_reference_rpc_fetches_fixed_provider_endpoints_inside_postgres():
    sql = _sql()

    assert "create extension if not exists http with schema extensions" in sql
    assert "append_big_move_reference_observation_v1(\n  p_binance_symbol text,\n  p_okx_inst_id text" in sql
    assert "drop function if exists public.append_big_move_reference_observation_v1(jsonb)" in sql
    assert "extensions.http_get(" in sql
    assert "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=" in sql
    assert "https://www.okx.com/api/v5/market/ticker?instId=" in sql
    assert "p_capture jsonb" not in sql
    assert "TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2" in sql
    assert "POSTGRES_HTTP_EXTENSION_FIXED_ENDPOINTS" in sql


def test_reference_rpc_rejects_cross_asset_or_stale_forged_values():
    sql = _sql()

    assert "v_binance_symbol !~ '^[A-Z0-9]{2,24}USDT$'" in sql
    assert "v_okx_inst_id !~ '^[A-Z0-9]{2,24}-USDT$'" in sql
    assert "v_okx_inst_id is distinct from (v_base || '-USDT')" in sql
    assert "v_binance_observed < v_now - interval '120 seconds'" in sql
    assert "v_okx_observed < v_now - interval '120 seconds'" in sql
    assert "if v_deviation_bps > 75" in sql
    assert "extensions.digest(convert_to(v_binance_content, 'UTF8'), 'sha256')" in sql
    assert "extensions.digest(convert_to(v_okx_content, 'UTF8'), 'sha256')" in sql
    assert "raw_response_utf8" in sql
    assert "raw_response_sha256" in sql


def test_forward_formation_store_rejects_stale_backdated_payloads():
    sql = _sql()

    assert "formation_payload ? 'formed_at'" in sql
    assert "formation_payload ? 'evidence_cutoff'" in sql
    assert "formation_payload ? 'reference_price_observed_at'" in sql
    assert "created_at - interval '5 minutes'" in sql
    assert "(formation_payload ->> 'formed_at')::timestamptz <= created_at" in sql
    assert "(formation_payload ->> 'reference_price_observed_at')::timestamptz <= created_at" in sql
    assert "(p_formation_payload ->> 'formed_at')::timestamptz < ref.created_at" in sql
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
    assert "ref.source_id is distinct from 'TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2'" in sql
    assert "'big_move_reference:' || ref.sequence::text" in sql
    assert "p_formation_payload ->> 'reference_price_observation_sha256'" in sql
    assert "p_formation_payload ->> 'reference_price_source_id'" in sql
    assert "p_formation_payload ->> 'reference_price_observed_at'" in sql
    assert "p_formation_payload ->> 'reference_price'" in sql
    assert "grant insert (forecast_fingerprint, formation_payload)" not in sql
    assert "security definer" in lowered

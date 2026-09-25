-- Close the relation-level check->use race in the trusted <=90d 2x prospective path.
--
-- #784/#785 already validate the live structural contract before formation/outcome/HIT
-- authority can be used. That validation was previously followed by an unguarded
-- interval before the delegate touched the authority-bearing relations. A concurrent
-- DDL transaction could therefore attempt to change a table/constraint/trigger after
-- validation but before use.
--
-- This migration takes transaction-scoped SHARE ROW EXCLUSIVE locks on all three
-- authority-bearing relations BEFORE catalog validation. PostgreSQL retains explicit
-- LOCK TABLE locks until transaction end, so the same locks remain held through the
-- delegate call. SHARE ROW EXCLUSIVE is intentionally stronger than ordinary writer
-- ROW EXCLUSIVE: it serializes these low-frequency truth-path calls and conflicts with
-- the lock modes used by relevant table/constraint/trigger DDL. A lock wait, deadlock,
-- missing relation, or incompatible DDL fails/serializes rather than falling back to a
-- weaker store.
--
-- Scope boundary: this closes the relation / constraint / table-trigger TOCTOU class.
-- It does NOT claim that relation locks freeze pg_proc function-definition replacement.
-- That separate object-definition race remains fail-closed as
-- PROSPECTIVE_SCHEMA_FUNCTION_DEFINITION_TOCTOU_NOT_YET_PROVEN until independently
-- disproven or protected by a separately reviewed mechanism.
--
-- Research only. No formation is backfilled. No candidate, model, promotion, broker,
-- spend, or trading authority is created.

create or replace function public.acquire_big_move_prospective_relation_locks_v1()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  begin
    lock table
      public.big_move_reference_observations,
      public.big_move_forward_formations,
      public.big_move_forward_outcome_observations
    in share row exclusive mode;
  exception
    when undefined_table then
      raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: relation lock target missing';
  end;
end;
$$;

revoke all on function public.acquire_big_move_prospective_relation_locks_v1()
  from public, anon, authenticated, service_role;

-- Replace only the three #784 guarded public entrypoints. Their scientific semantics,
-- argument/result contracts, delegate implementations, and service-role surface stay
-- unchanged. The only material change is lock -> validate -> use ordering.
create or replace function public.append_big_move_forward_formation_v1(
  p_forecast_fingerprint text,
  p_reference_observation_sequence bigint,
  p_formation_payload jsonb
) returns table(
  sequence bigint,
  forecast_fingerprint text,
  reference_observation_sequence bigint,
  reference_observation_created_at timestamptz,
  reference_observation jsonb,
  created_at timestamptz,
  formation_payload jsonb
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform public.acquire_big_move_prospective_relation_locks_v1();
  perform public.assert_big_move_prospective_schema_contract_v1();
  return query
    select * from public.append_big_move_forward_formation_v1_unguarded_784(
      p_forecast_fingerprint,
      p_reference_observation_sequence,
      p_formation_payload
    );
end;
$$;
revoke all on function public.append_big_move_forward_formation_v1(text, bigint, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_big_move_forward_formation_v1(text, bigint, jsonb)
  to service_role;

create or replace function public.append_big_move_forward_outcome_observation_v1(
  p_formation_sequence bigint
) returns table(
  sequence bigint,
  formation_sequence bigint,
  forecast_fingerprint text,
  formation_receipt_fingerprint text,
  source_reference_observation_sequence bigint,
  asset_id text,
  binance_symbol text,
  okx_inst_id text,
  observed_price numeric,
  observed_at timestamptz,
  captured_at timestamptz,
  source_evidence_sha256 text,
  binding_sha256 text,
  created_at timestamptz,
  source_reference_observation jsonb
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform public.acquire_big_move_prospective_relation_locks_v1();
  perform public.assert_big_move_prospective_schema_contract_v1();
  return query
    select * from public.append_big_move_forward_outcome_observation_v1_unguarded_784(
      p_formation_sequence
    );
end;
$$;
revoke all on function public.append_big_move_forward_outcome_observation_v1(bigint)
  from public, anon, authenticated;
grant execute on function public.append_big_move_forward_outcome_observation_v1(bigint)
  to service_role;

create or replace function public.derive_big_move_forward_hit_evidence_v1(
  p_formation_sequence bigint
) returns table(
  formation_sequence bigint,
  forecast_fingerprint text,
  formation_receipt_fingerprint text,
  target_price numeric,
  breach_observation jsonb
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform public.acquire_big_move_prospective_relation_locks_v1();
  perform public.assert_big_move_prospective_schema_contract_v1();
  return query
    select * from public.derive_big_move_forward_hit_evidence_v1_unguarded_784(
      p_formation_sequence
    );
end;
$$;
revoke all on function public.derive_big_move_forward_hit_evidence_v1(bigint)
  from public, anon, authenticated;
grant execute on function public.derive_big_move_forward_hit_evidence_v1(bigint)
  to service_role;

comment on function public.acquire_big_move_prospective_relation_locks_v1() is
  'Transaction-scoped relation lock barrier for #506 prospective schema check->use integrity; no function-definition TOCTOU authority.';

notify pgrst, 'reload schema';
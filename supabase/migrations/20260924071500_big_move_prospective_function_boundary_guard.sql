-- Harden the function-definition side of the trusted <=90d 2x prospective guard.
--
-- The first #784 guard intentionally checked SECURITY DEFINER and presence of a
-- search_path setting, but presence alone is too weak: `search_path=public` would
-- satisfy that predicate while reopening object-resolution risk. It also did not
-- freeze trusted-owner consistency across the public wrappers, quarantined delegates,
-- trigger rejector, and guard helpers.
--
-- This follow-up requires every authority-bearing routine to be owned by the same
-- role as this reviewed guard helper, to be SECURITY DEFINER, and to carry exactly
-- one function-local setting: search_path="". It also proves that no ordinary
-- application role can execute a quarantined delegate directly.
--
-- This is static-definition drift protection. It does not claim to serialize a
-- concurrent CREATE OR REPLACE FUNCTION by the trusted database owner after this
-- check but before delegate invocation. That narrow trusted-control-plane race remains
-- PROSPECTIVE_SCHEMA_FUNCTION_DEFINITION_TOCTOU_NOT_YET_PROVEN.

create or replace function public.assert_big_move_prospective_function_boundary_v1()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_expected_owner oid;
  v_fn oid;
  v_owner oid;
  v_security_definer boolean;
  v_config text[];
  v_rpc record;
begin
  select p.proowner
    into v_expected_owner
    from pg_catalog.pg_proc p
   where p.oid = to_regprocedure(
     'public.assert_big_move_prospective_function_boundary_v1()'
   );
  if v_expected_owner is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: function-boundary owner missing';
  end if;

  for v_rpc in
    select * from (values
      ('public.assert_big_move_prospective_schema_contract_v1()', 'schema guard'),
      ('public.acquire_big_move_prospective_relation_locks_v1()', 'relation lock guard'),
      ('public.assert_big_move_prospective_function_boundary_v1()', 'function guard'),
      ('public.append_big_move_reference_observation_v1(text,text)', 'reference append'),
      ('public.append_big_move_forward_formation_v1(text,bigint,jsonb)', 'formation wrapper'),
      ('public.append_big_move_forward_outcome_observation_v1(bigint)', 'outcome wrapper'),
      ('public.derive_big_move_forward_hit_evidence_v1(bigint)', 'hit wrapper'),
      ('public.reject_big_move_forward_outcome_observation_mutation_v1()', 'outcome rejector'),
      ('public.append_big_move_forward_formation_v1_unguarded_784(text,bigint,jsonb)', 'formation delegate'),
      ('public.append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)', 'outcome delegate'),
      ('public.derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)', 'hit delegate')
    ) e(signature, rpc_label)
  loop
    v_fn := to_regprocedure(v_rpc.signature);
    if v_fn is null then
      raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: % function missing',
        v_rpc.rpc_label;
    end if;

    select p.proowner, p.prosecdef, p.proconfig
      into v_owner, v_security_definer, v_config
      from pg_catalog.pg_proc p
     where p.oid = v_fn;

    if v_owner is distinct from v_expected_owner
       or not coalesce(v_security_definer, false)
       or coalesce(pg_catalog.array_length(v_config, 1), 0) <> 1
       or v_config[1] is distinct from 'search_path=""' then
      raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: % owner/security/search_path drift',
        v_rpc.rpc_label;
    end if;
  end loop;

  -- The renamed delegates are implementation details of the reviewed wrappers.
  -- PUBLIC inheritance and all ordinary Supabase application roles must remain unable
  -- to invoke them directly.
  for v_rpc in
    select * from (values
      ('public.append_big_move_forward_formation_v1_unguarded_784(text,bigint,jsonb)', 'formation'),
      ('public.append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)', 'outcome'),
      ('public.derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)', 'hit')
    ) e(signature, rpc_label)
  loop
    v_fn := to_regprocedure(v_rpc.signature);
    if v_fn is null
       or pg_catalog.has_function_privilege('service_role', v_fn, 'EXECUTE')
       or pg_catalog.has_function_privilege('authenticated', v_fn, 'EXECUTE')
       or pg_catalog.has_function_privilege('anon', v_fn, 'EXECUTE') then
      raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: % delegate execution boundary drift',
        v_rpc.rpc_label;
    end if;
  end loop;
end;
$$;

revoke all on function public.assert_big_move_prospective_function_boundary_v1()
  from public, anon, authenticated, service_role;

-- Preserve lock -> structural validation -> exact function-boundary validation -> use.
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
  perform public.assert_big_move_prospective_function_boundary_v1();
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
  perform public.assert_big_move_prospective_function_boundary_v1();
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
  perform public.assert_big_move_prospective_function_boundary_v1();
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

comment on function public.assert_big_move_prospective_function_boundary_v1() is
  'Exact owner/SECURITY DEFINER/empty-search_path/delegate-execution preflight for #506 prospective authority; trusted-owner concurrent function replacement remains separately unproven.';

notify pgrst, 'reload schema';
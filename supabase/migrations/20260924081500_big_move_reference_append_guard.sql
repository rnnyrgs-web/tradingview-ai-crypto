-- Close the remaining trusted <=90d 2x prospective write bypass: the reference
-- observation append itself must cross the same relation/schema/function barriers
-- as formation, outcome, and HIT evidence. Reference rows are upstream scientific
-- authority; allowing them to be minted after structural drift would taint every
-- downstream formation that cites them.
--
-- Keep the reviewed v2 provider/chronology implementation byte-for-byte reachable as
-- a quarantined delegate. The public service-role RPC becomes a thin fail-closed
-- wrapper. No historical rows are rewritten and no candidate/trading authority is
-- created.

alter function public.append_big_move_reference_observation_v1(text, text)
  rename to append_big_move_reference_observation_v1_unguarded_784;

revoke all on function public.append_big_move_reference_observation_v1_unguarded_784(text, text)
  from public, anon, authenticated, service_role;

-- Extend the exact function-definition boundary so the newly quarantined reference
-- delegate is authenticated under the same owner / SECURITY DEFINER / empty
-- search_path contract as every other prospective authority-bearing routine.
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
      ('public.append_big_move_reference_observation_v1(text,text)', 'reference wrapper'),
      ('public.append_big_move_forward_formation_v1(text,bigint,jsonb)', 'formation wrapper'),
      ('public.append_big_move_forward_outcome_observation_v1(bigint)', 'outcome wrapper'),
      ('public.derive_big_move_forward_hit_evidence_v1(bigint)', 'hit wrapper'),
      ('public.reject_big_move_forward_outcome_observation_mutation_v1()', 'outcome rejector'),
      ('public.append_big_move_reference_observation_v1_unguarded_784(text,text)', 'reference delegate'),
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

  for v_rpc in
    select * from (values
      ('public.append_big_move_reference_observation_v1_unguarded_784(text,text)', 'reference'),
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

create or replace function public.append_big_move_reference_observation_v1(
  p_binance_symbol text,
  p_okx_inst_id text
) returns table(
  sequence bigint,
  asset_id text,
  reference_price numeric,
  observed_at timestamptz,
  captured_at timestamptz,
  created_at timestamptz,
  source_id text,
  evidence_sha256 text,
  evidence jsonb
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
    select * from public.append_big_move_reference_observation_v1_unguarded_784(
      p_binance_symbol,
      p_okx_inst_id
    );
end;
$$;

revoke all on function public.append_big_move_reference_observation_v1(text, text)
  from public, anon, authenticated;
grant execute on function public.append_big_move_reference_observation_v1(text, text)
  to service_role;

comment on function public.append_big_move_reference_observation_v1(text, text) is
  'Fail-closed #784 prospective reference-evidence wrapper: relation lock -> structural guard -> function guard -> frozen v2 reference delegate.';

notify pgrst, 'reload schema';

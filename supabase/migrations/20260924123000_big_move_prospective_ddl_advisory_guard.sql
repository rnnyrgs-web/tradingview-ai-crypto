-- Serialize trusted <=90d prospective writes against authorized repository-managed
-- function DDL without pretending SQL can defend against a non-cooperative DB owner.
--
-- Threat model frozen by #785:
--   * ordinary application/runtime callers are untrusted and must cross reviewed RPCs;
--   * repository-managed DB migrations are trusted only when they obey this fixed
--     advisory-lock protocol and pass exact-head CI/review;
--   * intentional owner/admin DDL that ignores the protocol is a trusted-root /
--     control-plane compromise and is not claimed to be self-defendable by SQL.
--
-- Bootstrap safety: new-protocol wrappers take shared advisory -> relation locks, so
-- this migration MUST take the fixed exclusive advisory xact lock first. It then
-- takes relation locks to drain pre-protocol writers that know nothing about the
-- advisory protocol. This globally consistent order prevents a bootstrap deadlock
-- between a new writer already holding shared advisory and a migration holding the
-- relation locks while waiting for exclusive advisory. After this migration, every
-- public prospective write wrapper takes shared advisory before the existing
-- relation/schema/function barriers. Future reviewed migrations that touch this
-- authority surface must take acquire_big_move_prospective_ddl_write_lock_v1()
-- before DDL.
--
-- Frozen advisory key:
--   int64(first 8 bytes SHA256("big_move_prospective_authority_v1"))
--   = 6628152387724455858

-- Acquire the future protocol first so no new-protocol writer can enter behind us.
-- The lock is transaction-scoped. Pre-protocol writers do not take this lock, so
-- they continue until the relation-lock drain below reaches them.
select pg_catalog.pg_advisory_xact_lock(6628152387724455858);

-- Drain any pre-protocol authority writer that may already hold relation-level write
-- locks. With exclusive advisory already held, new-protocol writers wait before they
-- can acquire relation locks, eliminating the inverse lock-order cycle.
lock table
  public.big_move_reference_observations,
  public.big_move_forward_formations,
  public.big_move_forward_outcome_observations
in share row exclusive mode;

create or replace function public.acquire_big_move_prospective_ddl_read_lock_v1()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform pg_catalog.pg_advisory_xact_lock_shared(6628152387724455858);
end;
$$;

create or replace function public.acquire_big_move_prospective_ddl_write_lock_v1()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(6628152387724455858);
end;
$$;

-- These are internal control-plane primitives. Application callers reach the shared
-- lock only through the reviewed SECURITY DEFINER write wrappers. The exclusive lock
-- is for reviewed owner-run migrations, not an application RPC.
revoke all on function public.acquire_big_move_prospective_ddl_read_lock_v1()
  from public, anon, authenticated, service_role;
revoke all on function public.acquire_big_move_prospective_ddl_write_lock_v1()
  from public, anon, authenticated, service_role;

-- Extend the exact function-definition boundary to include both advisory-lock helpers.
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
      ('public.acquire_big_move_prospective_ddl_read_lock_v1()', 'DDL shared lock guard'),
      ('public.acquire_big_move_prospective_ddl_write_lock_v1()', 'DDL exclusive lock guard'),
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

  -- Internal helpers/delegates must not be directly executable by ordinary app roles.
  for v_rpc in
    select * from (values
      ('public.acquire_big_move_prospective_ddl_read_lock_v1()', 'DDL shared lock helper'),
      ('public.acquire_big_move_prospective_ddl_write_lock_v1()', 'DDL exclusive lock helper'),
      ('public.append_big_move_reference_observation_v1_unguarded_784(text,text)', 'reference delegate'),
      ('public.append_big_move_forward_formation_v1_unguarded_784(text,bigint,jsonb)', 'formation delegate'),
      ('public.append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)', 'outcome delegate'),
      ('public.derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)', 'hit delegate')
    ) e(signature, rpc_label)
  loop
    v_fn := to_regprocedure(v_rpc.signature);
    if v_fn is null
       or pg_catalog.has_function_privilege('service_role', v_fn, 'EXECUTE')
       or pg_catalog.has_function_privilege('authenticated', v_fn, 'EXECUTE')
       or pg_catalog.has_function_privilege('anon', v_fn, 'EXECUTE') then
      raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: % execution boundary drift',
        v_rpc.rpc_label;
    end if;
  end loop;
end;
$$;

revoke all on function public.assert_big_move_prospective_function_boundary_v1()
  from public, anon, authenticated, service_role;

-- Shared advisory lock MUST be first in every authority-bearing public wrapper. It
-- serializes the complete checked write transaction against authorized function DDL.
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
  perform public.acquire_big_move_prospective_ddl_read_lock_v1();
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
  perform public.acquire_big_move_prospective_ddl_read_lock_v1();
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
  perform public.acquire_big_move_prospective_ddl_read_lock_v1();
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
  perform public.acquire_big_move_prospective_ddl_read_lock_v1();
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

comment on function public.acquire_big_move_prospective_ddl_read_lock_v1() is
  'Shared xact advisory lock for #506 authority writes; serializes reviewed writes against cooperative repository-managed function DDL.';
comment on function public.acquire_big_move_prospective_ddl_write_lock_v1() is
  'Exclusive xact advisory lock for reviewed repository-managed #506 function DDL; intentional owner/admin bypass is a trusted-root compromise.';
comment on function public.assert_big_move_prospective_function_boundary_v1() is
  'Exact owner/SECURITY DEFINER/empty-search_path/internal-execute preflight for #506; authorized function DDL is serialized by the frozen advisory-lock protocol.';

notify pgrst, 'reload schema';

-- Fail-closed structural contract for the trusted <=90d 2x prospective truth path.
--
-- This migration deliberately does NOT trust supabase_migrations timestamps, names,
-- or "latest" version ordering. The runtime guard inspects the live pg_catalog
-- structure that actually carries formation/outcome authority. It is read-only:
-- it repairs nothing and raises PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN on drift.
--
-- The three authoritative entry points are wrapped so service_role cannot bypass
-- the guard through their pre-#784 implementations. The renamed delegates keep
-- their original semantics but have all non-owner EXECUTE privileges revoked.
-- Research only. No candidate, promotion, broker, spend, or trading authority.

create or replace function public.assert_big_move_prospective_schema_contract_v1()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_ref oid := to_regclass('public.big_move_reference_observations');
  v_form oid := to_regclass('public.big_move_forward_formations');
  v_out oid := to_regclass('public.big_move_forward_outcome_observations');
  v_checks text;
  v_default text;
  v_fn oid;
  v_result text;
  v_prosecdef boolean;
  v_proconfig text;
  v_trigger_fn oid := to_regprocedure('public.reject_big_move_forward_outcome_observation_mutation_v1()');
  v_internal oid;
  v_service_role oid := to_regrole('service_role');
begin
  -- Required relations must be real tables/partitioned tables, not views or aliases.
  if v_ref is null or not exists (
    select 1 from pg_catalog.pg_class where oid = v_ref and relkind in ('r', 'p')
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference table missing/incompatible';
  end if;
  if v_form is null or not exists (
    select 1 from pg_catalog.pg_class where oid = v_form and relkind in ('r', 'p')
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation table missing/incompatible';
  end if;
  if v_out is null or not exists (
    select 1 from pg_catalog.pg_class where oid = v_out and relkind in ('r', 'p')
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome table missing/incompatible';
  end if;

  -- Freeze only the columns that carry #506 authority. Harmless additive columns do
  -- not fail the guard, but every required type/nullability/identity property must
  -- match exactly. sequence must remain GENERATED ALWAYS identity.
  if exists (
    select 1
      from (values
        ('sequence', 'bigint', true, 'a'),
        ('asset_id', 'text', true, ''),
        ('source_id', 'text', true, ''),
        ('reference_price', 'numeric', true, ''),
        ('observed_at', 'timestamp with time zone', true, ''),
        ('captured_at', 'timestamp with time zone', true, ''),
        ('evidence_sha256', 'text', true, ''),
        ('evidence', 'jsonb', true, ''),
        ('created_at', 'timestamp with time zone', true, '')
      ) e(attname, typ, notnull, identity_kind)
      left join pg_catalog.pg_attribute a
        on a.attrelid = v_ref and a.attnum > 0 and not a.attisdropped
       and a.attname = e.attname
     where a.attnum is null
        or pg_catalog.format_type(a.atttypid, a.atttypmod) is distinct from e.typ
        or a.attnotnull is distinct from e.notnull
        or a.attidentity::text is distinct from e.identity_kind
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference column contract drift';
  end if;

  if exists (
    select 1
      from (values
        ('sequence', 'bigint', true, 'a'),
        ('forecast_fingerprint', 'text', true, ''),
        ('reference_observation_sequence', 'bigint', true, ''),
        ('formation_payload', 'jsonb', true, ''),
        ('created_at', 'timestamp with time zone', true, '')
      ) e(attname, typ, notnull, identity_kind)
      left join pg_catalog.pg_attribute a
        on a.attrelid = v_form and a.attnum > 0 and not a.attisdropped
       and a.attname = e.attname
     where a.attnum is null
        or pg_catalog.format_type(a.atttypid, a.atttypmod) is distinct from e.typ
        or a.attnotnull is distinct from e.notnull
        or a.attidentity::text is distinct from e.identity_kind
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation column contract drift';
  end if;

  if exists (
    select 1
      from (values
        ('sequence', 'bigint', true, 'a'),
        ('formation_sequence', 'bigint', true, ''),
        ('forecast_fingerprint', 'text', true, ''),
        ('formation_receipt_fingerprint', 'text', true, ''),
        ('source_reference_observation_sequence', 'bigint', true, ''),
        ('asset_id', 'text', true, ''),
        ('binance_symbol', 'text', true, ''),
        ('okx_inst_id', 'text', true, ''),
        ('observed_price', 'numeric', true, ''),
        ('observed_at', 'timestamp with time zone', true, ''),
        ('captured_at', 'timestamp with time zone', true, ''),
        ('source_evidence_sha256', 'text', true, ''),
        ('binding_sha256', 'text', true, ''),
        ('created_at', 'timestamp with time zone', true, '')
      ) e(attname, typ, notnull, identity_kind)
      left join pg_catalog.pg_attribute a
        on a.attrelid = v_out and a.attnum > 0 and not a.attisdropped
       and a.attname = e.attname
     where a.attnum is null
        or pg_catalog.format_type(a.atttypid, a.atttypmod) is distinct from e.typ
        or a.attnotnull is distinct from e.notnull
        or a.attidentity::text is distinct from e.identity_kind
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome column contract drift';
  end if;

  -- Server clocks are part of the non-backdateable receipt contract.
  select pg_catalog.pg_get_expr(d.adbin, d.adrelid)
    into v_default
    from pg_catalog.pg_attrdef d
    join pg_catalog.pg_attribute a
      on a.attrelid = d.adrelid and a.attnum = d.adnum
   where d.adrelid = v_ref and a.attname = 'created_at';
  if lower(coalesce(v_default, '')) <> 'clock_timestamp()' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference receipt clock drift';
  end if;
  select pg_catalog.pg_get_expr(d.adbin, d.adrelid)
    into v_default
    from pg_catalog.pg_attrdef d
    join pg_catalog.pg_attribute a
      on a.attrelid = d.adrelid and a.attnum = d.adnum
   where d.adrelid = v_form and a.attname = 'created_at';
  if lower(coalesce(v_default, '')) <> 'clock_timestamp()' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation receipt clock drift';
  end if;
  select pg_catalog.pg_get_expr(d.adbin, d.adrelid)
    into v_default
    from pg_catalog.pg_attrdef d
    join pg_catalog.pg_attribute a
      on a.attrelid = d.adrelid and a.attnum = d.adnum
   where d.adrelid = v_out and a.attname = 'created_at';
  if lower(coalesce(v_default, '')) <> 'clock_timestamp()' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome receipt clock drift';
  end if;

  -- RLS and the RPC-only mutation boundary must remain intact.
  if not (select relrowsecurity from pg_catalog.pg_class where oid = v_ref)
     or not (select relrowsecurity from pg_catalog.pg_class where oid = v_form)
     or not (select relrowsecurity from pg_catalog.pg_class where oid = v_out) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: required RLS disabled';
  end if;
  if v_service_role is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: service_role missing';
  end if;
  if not pg_catalog.has_table_privilege('service_role', v_ref, 'SELECT')
     or not pg_catalog.has_table_privilege('service_role', v_form, 'SELECT')
     or not pg_catalog.has_table_privilege('service_role', v_out, 'SELECT')
     or pg_catalog.has_table_privilege('service_role', v_ref, 'INSERT,UPDATE,DELETE,TRUNCATE')
     or pg_catalog.has_table_privilege('service_role', v_form, 'INSERT,UPDATE,DELETE,TRUNCATE')
     or pg_catalog.has_table_privilege('service_role', v_out, 'INSERT,UPDATE,DELETE,TRUNCATE') then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: service_role table privilege drift';
  end if;

  -- Primary, uniqueness, and exact linkage constraints. Auto-generated constraint
  -- names are intentionally irrelevant; semantic column/OID bindings are authority.
  if not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_ref and c.contype = 'p'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_ref and attname='sequence')]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_ref and c.contype = 'u'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_ref and attname='evidence_sha256')]::smallint[]
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference identity constraint missing';
  end if;

  if not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_form and c.contype = 'p'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_form and attname='sequence')]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_form and c.contype = 'u'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_form and attname='forecast_fingerprint')]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_form and c.contype = 'f' and c.confrelid = v_ref
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_form and attname='reference_observation_sequence')]::smallint[]
       and c.confkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_ref and attname='sequence')]::smallint[]
       and c.confupdtype = 'a' and c.confdeltype = 'a'
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation identity/linkage constraint missing';
  end if;

  if not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_out and c.contype = 'p'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='sequence')]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_out and c.contype = 'u'
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='binding_sha256')]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_out and c.contype = 'u'
       and c.conkey = array[
         (select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='formation_sequence'),
         (select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='source_reference_observation_sequence')
       ]::smallint[]
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_out and c.contype = 'f' and c.confrelid = v_form
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='formation_sequence')]::smallint[]
       and c.confkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_form and attname='sequence')]::smallint[]
       and c.confupdtype = 'a' and c.confdeltype = 'a'
  ) or not exists (
    select 1 from pg_catalog.pg_constraint c
     where c.conrelid = v_out and c.contype = 'f' and c.confrelid = v_ref
       and c.conkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_out and attname='source_reference_observation_sequence')]::smallint[]
       and c.confkey = array[(select attnum from pg_catalog.pg_attribute where attrelid=v_ref and attname='sequence')]::smallint[]
       and c.confupdtype = 'a' and c.confdeltype = 'a'
  ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome identity/linkage constraint missing';
  end if;

  -- Critical CHECK semantics. Whitespace/constraint names are not authority, but
  -- the live expressions protecting hashes, identity and chronology are required.
  select coalesce(string_agg(lower(pg_catalog.pg_get_constraintdef(c.oid, true)), E'\n'), '')
    into v_checks from pg_catalog.pg_constraint c
   where c.conrelid = v_ref and c.contype = 'c';
  if v_checks not like '%trusted_db_cross_venue_spot_reference_v2%'
     or v_checks not like '%trusted_db_cross_venue_reference_evidence.v2%'
     or v_checks not like '%reference_price >%'
     or v_checks not like '%evidence_sha256%[0-9a-f]%64%'
     or v_checks not like '%observed_at <= captured_at%'
     or v_checks not like '%captured_at <= created_at%'
     or not (v_checks like '%captured_at >=%created_at%' and v_checks like '%interval%') then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference CHECK contract drift';
  end if;

  select coalesce(string_agg(lower(pg_catalog.pg_get_constraintdef(c.oid, true)), E'\n'), '')
    into v_checks from pg_catalog.pg_constraint c
   where c.conrelid = v_form and c.contype = 'c';
  if v_checks not like '%forecast_fingerprint%[0-9a-f]%64%'
     or v_checks not like '%formation_payload%forecast_fingerprint%'
     or v_checks not like '%forward_move_forecast.v1%'
     or v_checks not like '%untrusted_until_server_receipt%'
     or v_checks not like '%formed_at%created_at%'
     or v_checks not like '%reference_price_observed_at%created_at%'
     or v_checks not like '%evidence_cutoff%formed_at%'
     or v_checks not like '%reference_price_observed_at%evidence_cutoff%' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation CHECK contract drift';
  end if;

  select coalesce(string_agg(lower(pg_catalog.pg_get_constraintdef(c.oid, true)), E'\n'), '')
    into v_checks from pg_catalog.pg_constraint c
   where c.conrelid = v_out and c.contype = 'c';
  if v_checks not like '%forecast_fingerprint%[0-9a-f]%64%'
     or v_checks not like '%formation_receipt_fingerprint%[0-9a-f]%64%'
     or v_checks not like '%source_evidence_sha256%[0-9a-f]%64%'
     or v_checks not like '%binding_sha256%[0-9a-f]%64%'
     or v_checks not like '%observed_price >%'
     or v_checks not like '%binance_symbol = asset_id%'
     or v_checks not like '%observed_at <= captured_at%'
     or v_checks not like '%captured_at <= created_at%' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome CHECK contract drift';
  end if;

  -- Exact RPC input + result signatures and SECURITY DEFINER/search_path hardening.
  v_fn := to_regprocedure('public.append_big_move_reference_observation_v1(text,text)');
  if v_fn is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference append RPC missing/wrong signature';
  end if;
  select p.prosecdef, coalesce(array_to_string(p.proconfig, ','), ''),
         regexp_replace(lower(pg_catalog.pg_get_function_result(p.oid)), '\s+', '', 'g')
    into v_prosecdef, v_proconfig, v_result
    from pg_catalog.pg_proc p where p.oid = v_fn;
  if not v_prosecdef or v_proconfig not like '%search_path=%'
     or v_result <> 'table(sequencebigint,asset_idtext,reference_pricenumeric,observed_attimestampwithtimezone,captured_attimestampwithtimezone,created_attimestampwithtimezone,source_idtext,evidence_sha256text,evidencejsonb)' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: reference append RPC contract drift';
  end if;

  v_fn := to_regprocedure('public.append_big_move_forward_formation_v1(text,bigint,jsonb)');
  if v_fn is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation append RPC missing/wrong signature';
  end if;
  select p.prosecdef, coalesce(array_to_string(p.proconfig, ','), ''),
         regexp_replace(lower(pg_catalog.pg_get_function_result(p.oid)), '\s+', '', 'g')
    into v_prosecdef, v_proconfig, v_result
    from pg_catalog.pg_proc p where p.oid = v_fn;
  if not v_prosecdef or v_proconfig not like '%search_path=%'
     or v_result <> 'table(sequencebigint,forecast_fingerprinttext,reference_observation_sequencebigint,reference_observation_created_attimestampwithtimezone,reference_observationjsonb,created_attimestampwithtimezone,formation_payloadjsonb)' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation append RPC contract drift';
  end if;

  v_fn := to_regprocedure('public.append_big_move_forward_outcome_observation_v1(bigint)');
  if v_fn is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome append RPC missing/wrong signature';
  end if;
  select p.prosecdef, coalesce(array_to_string(p.proconfig, ','), ''),
         regexp_replace(lower(pg_catalog.pg_get_function_result(p.oid)), '\s+', '', 'g')
    into v_prosecdef, v_proconfig, v_result
    from pg_catalog.pg_proc p where p.oid = v_fn;
  if not v_prosecdef or v_proconfig not like '%search_path=%'
     or v_result <> 'table(sequencebigint,formation_sequencebigint,forecast_fingerprinttext,formation_receipt_fingerprinttext,source_reference_observation_sequencebigint,asset_idtext,binance_symboltext,okx_inst_idtext,observed_pricenumeric,observed_attimestampwithtimezone,captured_attimestampwithtimezone,source_evidence_sha256text,binding_sha256text,created_attimestampwithtimezone,source_reference_observationjsonb)' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome append RPC contract drift';
  end if;

  v_fn := to_regprocedure('public.derive_big_move_forward_hit_evidence_v1(bigint)');
  if v_fn is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: hit derive RPC missing/wrong signature';
  end if;
  select p.prosecdef, coalesce(array_to_string(p.proconfig, ','), ''),
         regexp_replace(lower(pg_catalog.pg_get_function_result(p.oid)), '\s+', '', 'g')
    into v_prosecdef, v_proconfig, v_result
    from pg_catalog.pg_proc p where p.oid = v_fn;
  if not v_prosecdef or v_proconfig not like '%search_path=%'
     or v_result <> 'table(formation_sequencebigint,forecast_fingerprinttext,formation_receipt_fingerprinttext,target_pricenumeric,breach_observationjsonb)' then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: hit derive RPC contract drift';
  end if;

  -- The outcome table must retain an enabled BEFORE ROW UPDATE OR DELETE rejector
  -- bound to the exact trigger function. PostgreSQL tgtype 27 = ROW|BEFORE|DELETE|UPDATE.
  if v_trigger_fn is null then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome mutation-rejection function missing';
  end if;
  select p.prosecdef, coalesce(array_to_string(p.proconfig, ','), '')
    into v_prosecdef, v_proconfig
    from pg_catalog.pg_proc p
   where p.oid = v_trigger_fn and p.prorettype = 'pg_catalog.trigger'::regtype;
  if not coalesce(v_prosecdef, false) or v_proconfig not like '%search_path=%'
     or not exists (
       select 1
         from pg_catalog.pg_trigger t
        where t.tgrelid = v_out
          and t.tgname = 'big_move_forward_outcome_observations_append_only'
          and not t.tgisinternal
          and t.tgenabled = 'O'
          and t.tgtype = 27
          and t.tgfoid = v_trigger_fn
     ) then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome mutation-rejection trigger drift';
  end if;

  -- Renamed pre-guard delegates exist only so the guarded wrappers can reuse proven
  -- implementation. service_role (including PUBLIC inheritance) must not EXECUTE them.
  v_internal := to_regprocedure('public.append_big_move_forward_formation_v1_unguarded_784(text,bigint,jsonb)');
  if v_internal is null or pg_catalog.has_function_privilege('service_role', v_internal, 'EXECUTE') then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: formation guard bypass exposed';
  end if;
  v_internal := to_regprocedure('public.append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)');
  if v_internal is null or pg_catalog.has_function_privilege('service_role', v_internal, 'EXECUTE') then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: outcome guard bypass exposed';
  end if;
  v_internal := to_regprocedure('public.derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)');
  if v_internal is null or pg_catalog.has_function_privilege('service_role', v_internal, 'EXECUTE') then
    raise exception 'PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN: hit guard bypass exposed';
  end if;
end;
$$;

revoke all on function public.assert_big_move_prospective_schema_contract_v1()
  from public, anon, authenticated;
grant execute on function public.assert_big_move_prospective_schema_contract_v1()
  to service_role;

-- Quarantine the pre-guard delegates from every ordinary application role. The
-- wrapper owner may still invoke them inside SECURITY DEFINER after a green preflight.
alter function public.append_big_move_forward_formation_v1(text, bigint, jsonb)
  rename to append_big_move_forward_formation_v1_unguarded_784;
revoke all on function public.append_big_move_forward_formation_v1_unguarded_784(text, bigint, jsonb)
  from public, anon, authenticated, service_role;

create function public.append_big_move_forward_formation_v1(
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

alter function public.append_big_move_forward_outcome_observation_v1(bigint)
  rename to append_big_move_forward_outcome_observation_v1_unguarded_784;
revoke all on function public.append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)
  from public, anon, authenticated, service_role;

create function public.append_big_move_forward_outcome_observation_v1(
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

alter function public.derive_big_move_forward_hit_evidence_v1(bigint)
  rename to derive_big_move_forward_hit_evidence_v1_unguarded_784;
revoke all on function public.derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)
  from public, anon, authenticated, service_role;

create function public.derive_big_move_forward_hit_evidence_v1(
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

comment on function public.assert_big_move_prospective_schema_contract_v1() is
  'Read-only structural preflight for #506 trusted prospective formation/outcome/HIT authority. Migration chronology is diagnostic only.';

notify pgrst, 'reload schema';

-- Trusted post-formation price-path observations for <=90d 2x research.
--
-- Public hashes prove integrity, not durable origin.  This boundary therefore:
--   * accepts only a persisted formation sequence for provider acquisition;
--   * derives forecast + formation-receipt identity from the stored formation;
--   * binds canonical asset and exact Binance/OKX spot instruments into every row;
--   * keeps the table append-only; and
--   * exposes non-final HIT evidence only through a DB-owned query over stored rows.
--
-- This migration does NOT create final HIT/EXPIRED/INVALIDATED resolutions.  The
-- DB-owned HIT RPC proves only that at least one durable sampled observation breached
-- the frozen target.  It does not establish the true first market crossing or grant
-- factory metrics, promotion, broker, or live-trading authority.

create table if not exists public.big_move_forward_outcome_observations (
  sequence bigint generated always as identity primary key,
  formation_sequence bigint not null
    references public.big_move_forward_formations(sequence),
  forecast_fingerprint text not null
    check (forecast_fingerprint ~ '^[0-9a-f]{64}$'),
  formation_receipt_fingerprint text not null
    check (formation_receipt_fingerprint ~ '^[0-9a-f]{64}$'),
  source_reference_observation_sequence bigint not null
    references public.big_move_reference_observations(sequence),
  asset_id text not null check (length(btrim(asset_id)) > 0),
  binance_symbol text not null check (length(btrim(binance_symbol)) > 0),
  okx_inst_id text not null check (length(btrim(okx_inst_id)) > 0),
  observed_price numeric not null check (observed_price > 0),
  observed_at timestamptz not null,
  captured_at timestamptz not null,
  source_evidence_sha256 text not null
    check (source_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  binding_sha256 text not null unique
    check (binding_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (formation_sequence, source_reference_observation_sequence),
  check (binance_symbol = asset_id),
  check (observed_at <= captured_at),
  check (captured_at <= created_at)
);

comment on table public.big_move_forward_outcome_observations is
  'Append-only DB-fetched two-venue spot outcome observations bound to exact trusted <=90d 2x formation identity; research only, not a final resolution.';

alter table public.big_move_forward_outcome_observations enable row level security;

revoke all on table public.big_move_forward_outcome_observations
  from public, anon, authenticated, service_role;
grant select on table public.big_move_forward_outcome_observations to service_role;

revoke all on sequence public.big_move_forward_outcome_observations_sequence_seq
  from public, anon, authenticated, service_role;
grant usage, select on sequence public.big_move_forward_outcome_observations_sequence_seq
  to service_role;

create or replace function public.reject_big_move_forward_outcome_observation_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception 'big-move forward outcome observations are append-only';
end;
$$;

revoke all on function public.reject_big_move_forward_outcome_observation_mutation_v1()
  from public, anon, authenticated;

drop trigger if exists big_move_forward_outcome_observations_append_only
  on public.big_move_forward_outcome_observations;
create trigger big_move_forward_outcome_observations_append_only
before update or delete on public.big_move_forward_outcome_observations
for each row execute function public.reject_big_move_forward_outcome_observation_mutation_v1();

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
declare
  formation public.big_move_forward_formations%rowtype;
  source_ref record;
  existing public.big_move_forward_outcome_observations%rowtype;
  v_now timestamptz;
  v_asset_id text;
  v_base text;
  v_binance_symbol text;
  v_okx_inst_id text;
  v_horizon_days integer;
  v_expires_at timestamptz;
  v_formation_created_iso text;
  v_formation_receipt_preimage text;
  v_formation_receipt_sha text;
  v_observed_price_text text;
  v_observed_iso text;
  v_captured_iso text;
  v_binding_preimage text;
  v_binding_sha text;
begin
  if p_formation_sequence is null or p_formation_sequence <= 0 then
    raise exception 'invalid trusted formation sequence';
  end if;

  select * into formation
    from public.big_move_forward_formations f
    where f.sequence = p_formation_sequence;
  if not found then
    raise exception 'missing trusted forward formation';
  end if;

  if formation.formation_payload ->> 'schema' is distinct from 'forward_move_forecast.v1'
     or formation.formation_payload ->> 'forecast_fingerprint'
          is distinct from formation.forecast_fingerprint then
    raise exception 'persisted forward formation contract mismatch';
  end if;

  v_asset_id := upper(btrim(coalesce(formation.formation_payload ->> 'asset_id', '')));
  if v_asset_id !~ '^[A-Z0-9]{2,24}USDT$'
     or v_asset_id is distinct from (formation.formation_payload ->> 'asset_id') then
    raise exception 'trusted outcome formation asset is not an admitted USDT spot identity';
  end if;
  v_base := substring(v_asset_id from '^([A-Z0-9]{2,24})USDT$');
  if v_base is null then
    raise exception 'trusted outcome formation asset identity invalid';
  end if;
  v_binance_symbol := v_asset_id;
  v_okx_inst_id := v_base || '-USDT';

  begin
    v_horizon_days := (formation.formation_payload ->> 'horizon_days')::integer;
  exception when others then
    raise exception 'trusted outcome formation horizon invalid';
  end;
  if v_horizon_days < 1 or v_horizon_days > 90 then
    raise exception 'trusted outcome formation horizon outside frozen bounds';
  end if;
  v_expires_at := formation.created_at + make_interval(days => v_horizon_days);

  -- This cross-language receipt identity is derived only from the persisted row.
  -- The forecast fingerprint already commits the complete frozen formation payload.
  v_formation_created_iso := to_char(
    formation.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );
  v_formation_receipt_preimage :=
      'trusted_forward_formation_receipt_binding.v1' || E'\n'
      || formation.sequence::text || E'\n'
      || formation.forecast_fingerprint || E'\n'
      || v_formation_created_iso;
  v_formation_receipt_sha := encode(
    extensions.digest(convert_to(v_formation_receipt_preimage, 'UTF8'), 'sha256'), 'hex'
  );

  -- Reuse the hardened DB-owned provider boundary.  Instruments are derived above;
  -- no caller-controlled venue/symbol reaches the fetch function.
  select * into source_ref
    from public.append_big_move_reference_observation_v1(v_binance_symbol, v_okx_inst_id);
  if not found then
    raise exception 'trusted outcome provider observation was not returned';
  end if;

  v_now := clock_timestamp();
  if source_ref.asset_id is distinct from v_asset_id
     or source_ref.source_id is distinct from 'TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2'
     or source_ref.observed_at <= formation.created_at
     or source_ref.captured_at <= formation.created_at
     or source_ref.created_at <= formation.created_at
     or source_ref.observed_at > v_expires_at
     or source_ref.captured_at > v_expires_at
     or source_ref.created_at > v_now
     or source_ref.evidence_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'trusted outcome provider observation violates formation identity or chronology';
  end if;

  if source_ref.evidence ->> 'asset_id' is distinct from v_asset_id
     or source_ref.evidence -> 'providers' -> 0 ->> 'venue' is distinct from 'BINANCE_SPOT'
     or source_ref.evidence -> 'providers' -> 0 ->> 'symbol' is distinct from v_binance_symbol
     or source_ref.evidence -> 'providers' -> 1 ->> 'venue' is distinct from 'OKX_SPOT'
     or source_ref.evidence -> 'providers' -> 1 ->> 'symbol' is distinct from v_okx_inst_id then
    raise exception 'trusted outcome provider venue/instrument identity mismatch';
  end if;

  v_observed_price_text := trim_scale(source_ref.reference_price)::text;
  v_observed_iso := to_char(
    source_ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );
  v_captured_iso := to_char(
    source_ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );
  v_binding_preimage :=
      'trusted_forward_outcome_observation.v2' || E'\n'
      || formation.sequence::text || E'\n'
      || formation.forecast_fingerprint || E'\n'
      || v_formation_receipt_sha || E'\n'
      || v_asset_id || E'\n'
      || 'BINANCE_SPOT' || E'\n'
      || v_binance_symbol || E'\n'
      || 'OKX_SPOT' || E'\n'
      || v_okx_inst_id || E'\n'
      || source_ref.sequence::text || E'\n'
      || source_ref.evidence_sha256 || E'\n'
      || v_observed_price_text || E'\n'
      || v_observed_iso || E'\n'
      || v_captured_iso;
  v_binding_sha := encode(
    extensions.digest(convert_to(v_binding_preimage, 'UTF8'), 'sha256'), 'hex'
  );

  perform pg_advisory_xact_lock(
    hashtextextended('big_move_forward_outcome_observations:' || v_binding_sha, 0)
  );

  select * into existing
    from public.big_move_forward_outcome_observations o
    where o.binding_sha256 = v_binding_sha;
  if found then
    if existing.formation_sequence is distinct from formation.sequence
       or existing.forecast_fingerprint is distinct from formation.forecast_fingerprint
       or existing.formation_receipt_fingerprint is distinct from v_formation_receipt_sha
       or existing.source_reference_observation_sequence is distinct from source_ref.sequence
       or existing.asset_id is distinct from v_asset_id
       or existing.binance_symbol is distinct from v_binance_symbol
       or existing.okx_inst_id is distinct from v_okx_inst_id then
      raise exception 'immutable trusted outcome observation conflict';
    end if;
    return query
      select existing.sequence,
             existing.formation_sequence,
             existing.forecast_fingerprint,
             existing.formation_receipt_fingerprint,
             existing.source_reference_observation_sequence,
             existing.asset_id,
             existing.binance_symbol,
             existing.okx_inst_id,
             existing.observed_price,
             existing.observed_at,
             existing.captured_at,
             existing.source_evidence_sha256,
             existing.binding_sha256,
             existing.created_at,
             jsonb_build_object(
               'sequence', source_ref.sequence,
               'asset_id', source_ref.asset_id,
               'reference_price', trim_scale(source_ref.reference_price)::text,
               'observed_at', to_char(source_ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'captured_at', to_char(source_ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'created_at', to_char(source_ref.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'source_id', source_ref.source_id,
               'evidence_sha256', source_ref.evidence_sha256,
               'evidence', source_ref.evidence
             );
    return;
  end if;

  return query
    insert into public.big_move_forward_outcome_observations(
      formation_sequence,
      forecast_fingerprint,
      formation_receipt_fingerprint,
      source_reference_observation_sequence,
      asset_id,
      binance_symbol,
      okx_inst_id,
      observed_price,
      observed_at,
      captured_at,
      source_evidence_sha256,
      binding_sha256,
      created_at
    ) values (
      formation.sequence,
      formation.forecast_fingerprint,
      v_formation_receipt_sha,
      source_ref.sequence,
      v_asset_id,
      v_binance_symbol,
      v_okx_inst_id,
      source_ref.reference_price,
      source_ref.observed_at,
      source_ref.captured_at,
      source_ref.evidence_sha256,
      v_binding_sha,
      clock_timestamp()
    )
    returning big_move_forward_outcome_observations.sequence,
              big_move_forward_outcome_observations.formation_sequence,
              big_move_forward_outcome_observations.forecast_fingerprint,
              big_move_forward_outcome_observations.formation_receipt_fingerprint,
              big_move_forward_outcome_observations.source_reference_observation_sequence,
              big_move_forward_outcome_observations.asset_id,
              big_move_forward_outcome_observations.binance_symbol,
              big_move_forward_outcome_observations.okx_inst_id,
              big_move_forward_outcome_observations.observed_price,
              big_move_forward_outcome_observations.observed_at,
              big_move_forward_outcome_observations.captured_at,
              big_move_forward_outcome_observations.source_evidence_sha256,
              big_move_forward_outcome_observations.binding_sha256,
              big_move_forward_outcome_observations.created_at,
              jsonb_build_object(
                'sequence', source_ref.sequence,
                'asset_id', source_ref.asset_id,
                'reference_price', trim_scale(source_ref.reference_price)::text,
                'observed_at', to_char(source_ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'captured_at', to_char(source_ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'created_at', to_char(source_ref.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'source_id', source_ref.source_id,
                'evidence_sha256', source_ref.evidence_sha256,
                'evidence', source_ref.evidence
              );
end;
$$;

revoke all on function public.append_big_move_forward_outcome_observation_v1(bigint)
  from public, anon, authenticated;
grant execute on function public.append_big_move_forward_outcome_observation_v1(bigint)
  to service_role;


-- Trusted non-final HIT evidence must originate from durable membership, not from a
-- caller handing Python a self-consistent row.  This RPC selects the sampled breach
-- directly from the append-only table and joins the exact retained provider receipt.
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
declare
  formation public.big_move_forward_formations%rowtype;
  hit public.big_move_forward_outcome_observations%rowtype;
  source_ref public.big_move_reference_observations%rowtype;
  v_asset_id text;
  v_base text;
  v_binance_symbol text;
  v_okx_inst_id text;
  v_horizon_days integer;
  v_expires_at timestamptz;
  v_reference_price numeric;
  v_target_multiple numeric;
  v_target_price numeric;
  v_formation_created_iso text;
  v_formation_receipt_preimage text;
  v_formation_receipt_sha text;
begin
  if p_formation_sequence is null or p_formation_sequence <= 0 then
    raise exception 'invalid trusted formation sequence';
  end if;

  select * into formation
    from public.big_move_forward_formations f
    where f.sequence = p_formation_sequence;
  if not found then
    raise exception 'missing trusted forward formation';
  end if;

  if formation.formation_payload ->> 'schema' is distinct from 'forward_move_forecast.v1'
     or formation.formation_payload ->> 'forecast_fingerprint'
          is distinct from formation.forecast_fingerprint then
    raise exception 'persisted forward formation contract mismatch';
  end if;

  v_asset_id := upper(btrim(coalesce(formation.formation_payload ->> 'asset_id', '')));
  if v_asset_id !~ '^[A-Z0-9]{2,24}USDT$'
     or v_asset_id is distinct from (formation.formation_payload ->> 'asset_id') then
    raise exception 'trusted HIT formation asset invalid';
  end if;
  v_base := substring(v_asset_id from '^([A-Z0-9]{2,24})USDT$');
  if v_base is null then
    raise exception 'trusted HIT formation asset identity invalid';
  end if;
  v_binance_symbol := v_asset_id;
  v_okx_inst_id := v_base || '-USDT';

  begin
    v_horizon_days := (formation.formation_payload ->> 'horizon_days')::integer;
    v_reference_price := (formation.formation_payload ->> 'reference_price')::numeric;
    v_target_multiple := (formation.formation_payload ->> 'target_multiple')::numeric;
  exception when others then
    raise exception 'trusted HIT frozen numeric contract malformed';
  end;
  if v_horizon_days < 1 or v_horizon_days > 90
     or v_reference_price <= 0
     or v_target_multiple < 2 then
    raise exception 'trusted HIT frozen numeric contract outside bounds';
  end if;
  v_expires_at := formation.created_at + make_interval(days => v_horizon_days);
  v_target_price := v_reference_price * v_target_multiple;

  v_formation_created_iso := to_char(
    formation.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );
  v_formation_receipt_preimage :=
      'trusted_forward_formation_receipt_binding.v1' || E'\n'
      || formation.sequence::text || E'\n'
      || formation.forecast_fingerprint || E'\n'
      || v_formation_created_iso;
  v_formation_receipt_sha := encode(
    extensions.digest(convert_to(v_formation_receipt_preimage, 'UTF8'), 'sha256'), 'hex'
  );

  -- Any durable row under this formation with mismatched subject/receipt identity is
  -- corruption, not evidence to skip.  Fail closed before looking for a breach.
  if exists (
    select 1
      from public.big_move_forward_outcome_observations o
      left join public.big_move_reference_observations r
        on r.sequence = o.source_reference_observation_sequence
     where o.formation_sequence = formation.sequence
       and (
         o.forecast_fingerprint is distinct from formation.forecast_fingerprint
         or o.formation_receipt_fingerprint is distinct from v_formation_receipt_sha
         or o.asset_id is distinct from v_asset_id
         or o.binance_symbol is distinct from v_binance_symbol
         or o.okx_inst_id is distinct from v_okx_inst_id
         or r.sequence is null
         or r.asset_id is distinct from o.asset_id
         or r.evidence_sha256 is distinct from o.source_evidence_sha256
         or r.reference_price is distinct from o.observed_price
         or r.observed_at is distinct from o.observed_at
         or r.captured_at is distinct from o.captured_at
         or r.evidence -> 'providers' -> 0 ->> 'venue' is distinct from 'BINANCE_SPOT'
         or r.evidence -> 'providers' -> 0 ->> 'symbol' is distinct from o.binance_symbol
         or r.evidence -> 'providers' -> 1 ->> 'venue' is distinct from 'OKX_SPOT'
         or r.evidence -> 'providers' -> 1 ->> 'symbol' is distinct from o.okx_inst_id
       )
  ) then
    raise exception 'durable trusted outcome membership or subject identity mismatch';
  end if;

  -- Deterministic sampled-breach choice only.  This is deliberately not final
  -- time-to-event semantics and makes no claim that the selected sample is the true
  -- first market crossing between observations.
  select o.* into hit
    from public.big_move_forward_outcome_observations o
    where o.formation_sequence = formation.sequence
      and o.forecast_fingerprint = formation.forecast_fingerprint
      and o.formation_receipt_fingerprint = v_formation_receipt_sha
      and o.asset_id = v_asset_id
      and o.binance_symbol = v_binance_symbol
      and o.okx_inst_id = v_okx_inst_id
      and o.observed_at > formation.created_at
      and o.captured_at > formation.created_at
      and o.observed_at <= v_expires_at
      and o.captured_at <= v_expires_at
      and o.observed_price >= v_target_price
    order by o.observed_at, o.captured_at, o.sequence
    limit 1;
  if not found then
    return;
  end if;

  select * into source_ref
    from public.big_move_reference_observations r
    where r.sequence = hit.source_reference_observation_sequence;
  if not found then
    raise exception 'trusted HIT source observation missing';
  end if;

  return query
    select formation.sequence,
           formation.forecast_fingerprint,
           v_formation_receipt_sha,
           v_target_price,
           jsonb_build_object(
             'sequence', hit.sequence,
             'formation_sequence', hit.formation_sequence,
             'forecast_fingerprint', hit.forecast_fingerprint,
             'formation_receipt_fingerprint', hit.formation_receipt_fingerprint,
             'source_reference_observation_sequence', hit.source_reference_observation_sequence,
             'asset_id', hit.asset_id,
             'binance_symbol', hit.binance_symbol,
             'okx_inst_id', hit.okx_inst_id,
             'observed_price', trim_scale(hit.observed_price)::text,
             'observed_at', to_char(hit.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
             'captured_at', to_char(hit.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
             'source_evidence_sha256', hit.source_evidence_sha256,
             'binding_sha256', hit.binding_sha256,
             'created_at', to_char(hit.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
             'source_reference_observation', jsonb_build_object(
               'sequence', source_ref.sequence,
               'asset_id', source_ref.asset_id,
               'reference_price', trim_scale(source_ref.reference_price)::text,
               'observed_at', to_char(source_ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'captured_at', to_char(source_ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'created_at', to_char(source_ref.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'source_id', source_ref.source_id,
               'evidence_sha256', source_ref.evidence_sha256,
               'evidence', source_ref.evidence
             )
           );
end;
$$;

revoke all on function public.derive_big_move_forward_hit_evidence_v1(bigint)
  from public, anon, authenticated;
grant execute on function public.derive_big_move_forward_hit_evidence_v1(bigint)
  to service_role;

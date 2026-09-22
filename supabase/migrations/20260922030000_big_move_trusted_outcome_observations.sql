-- Trusted post-formation price-path observations for <=90d 2x research.
--
-- This boundary deliberately accepts only a persisted formation sequence.  The
-- authoritative database derives the asset and exact Binance/OKX spot instruments
-- from that immutable formation, invokes the already-hardened DB-fetched two-venue
-- reference observation function, and binds the resulting provider evidence to the
-- exact formation.  Callers cannot submit price, timestamp, venue, symbol, provider
-- bytes, evidence digest, or binding digest.
--
-- This migration does NOT create final HIT/EXPIRED/INVALIDATED resolutions.  It only
-- creates append-only, provider-authenticated post-formation path evidence.  Broker
-- and live-trading authority remain absent.

create table if not exists public.big_move_forward_outcome_observations (
  sequence bigint generated always as identity primary key,
  formation_sequence bigint not null
    references public.big_move_forward_formations(sequence),
  formation_fingerprint text not null
    check (formation_fingerprint ~ '^[0-9a-f]{64}$'),
  source_reference_observation_sequence bigint not null
    references public.big_move_reference_observations(sequence),
  asset_id text not null check (length(btrim(asset_id)) > 0),
  observed_price numeric not null check (observed_price > 0),
  observed_at timestamptz not null,
  captured_at timestamptz not null,
  source_evidence_sha256 text not null
    check (source_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  binding_sha256 text not null unique
    check (binding_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (formation_sequence, source_reference_observation_sequence),
  check (observed_at <= captured_at),
  check (captured_at <= created_at)
);

comment on table public.big_move_forward_outcome_observations is
  'Append-only DB-fetched two-venue spot outcome observations bound to one trusted <=90d 2x formation; research only, not a final resolution.';

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
  formation_fingerprint text,
  source_reference_observation_sequence bigint,
  asset_id text,
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
  v_okx_inst_id text;
  v_horizon_days integer;
  v_expires_at timestamptz;
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

  -- Reuse the hardened DB-owned provider boundary.  Instruments are derived above;
  -- no caller-controlled venue/symbol reaches the fetch function.
  select * into source_ref
    from public.append_big_move_reference_observation_v1(v_asset_id, v_okx_inst_id);
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

  -- Defensive re-check of the retained provider identities before binding.  The
  -- source RPC already enforces these; repeating them here prevents a future source
  -- contract change from silently widening this outcome contract.
  if source_ref.evidence ->> 'asset_id' is distinct from v_asset_id
     or source_ref.evidence -> 'providers' -> 0 ->> 'venue' is distinct from 'BINANCE_SPOT'
     or source_ref.evidence -> 'providers' -> 0 ->> 'symbol' is distinct from v_asset_id
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
      'trusted_forward_outcome_observation.v1' || E'\n'
      || formation.sequence::text || E'\n'
      || formation.forecast_fingerprint || E'\n'
      || source_ref.sequence::text || E'\n'
      || v_asset_id || E'\n'
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
       or existing.source_reference_observation_sequence is distinct from source_ref.sequence then
      raise exception 'immutable trusted outcome observation conflict';
    end if;
    return query
      select existing.sequence,
             existing.formation_sequence,
             existing.formation_fingerprint,
             existing.source_reference_observation_sequence,
             existing.asset_id,
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
      formation_fingerprint,
      source_reference_observation_sequence,
      asset_id,
      observed_price,
      observed_at,
      captured_at,
      source_evidence_sha256,
      binding_sha256,
      created_at
    ) values (
      formation.sequence,
      formation.forecast_fingerprint,
      source_ref.sequence,
      v_asset_id,
      source_ref.reference_price,
      source_ref.observed_at,
      source_ref.captured_at,
      source_ref.evidence_sha256,
      v_binding_sha,
      clock_timestamp()
    )
    returning big_move_forward_outcome_observations.sequence,
              big_move_forward_outcome_observations.formation_sequence,
              big_move_forward_outcome_observations.formation_fingerprint,
              big_move_forward_outcome_observations.source_reference_observation_sequence,
              big_move_forward_outcome_observations.asset_id,
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

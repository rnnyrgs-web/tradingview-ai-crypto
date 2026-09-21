-- Research-only durable chronology for <=90d 2x+ forward forecasts.
--
-- Two append-only receipts are deliberately separated:
--   1) a contemporaneous reference-price observation receipt;
--   2) a forecast-formation receipt that MUST consume that stored observation.
--
-- This migration closes the durable reference/formation binding path. It does NOT by
-- itself prove that a caller-supplied reference capture originated from Binance/OKX;
-- provider-origin authentication remains a separate required service-boundary gate.
-- No table/function in this migration grants prediction, promotion, broker or trade
-- authority.

create table if not exists public.big_move_reference_observations (
  sequence bigint generated always as identity primary key,
  asset_id text not null check (length(btrim(asset_id)) > 0),
  source_id text not null
    check (source_id = 'TRUSTED_CROSS_VENUE_SPOT_REFERENCE_V1'),
  reference_price numeric not null check (reference_price > 0),
  observed_at timestamptz not null,
  captured_at timestamptz not null,
  evidence_sha256 text not null unique
    check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null,
  created_at timestamptz not null default clock_timestamp(),
  check (observed_at <= captured_at),
  check (captured_at <= created_at),
  check (captured_at >= created_at - interval '5 minutes'),
  check (evidence ->> 'schema' = 'trusted_cross_venue_reference_evidence.v1'),
  check (evidence ->> 'source_id' = source_id),
  check (evidence ->> 'asset_id' = asset_id),
  check ((evidence ->> 'reference_price')::numeric = reference_price),
  check (octet_length(evidence::text) <= 200000)
);

comment on table public.big_move_reference_observations is
  'Append-only DB-time receipts for <=90d 2x reference observations. Durable receipt is necessary but not sufficient for provider-origin authenticity.';

alter table public.big_move_reference_observations enable row level security;

revoke all on table public.big_move_reference_observations
  from public, anon, authenticated, service_role;
grant select on table public.big_move_reference_observations to service_role;

revoke all on sequence public.big_move_reference_observations_sequence_seq
  from public, anon, authenticated, service_role;
grant usage, select on sequence public.big_move_reference_observations_sequence_seq
  to service_role;

create or replace function public.append_big_move_reference_observation_v1(
  p_capture jsonb
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
declare
  v_now timestamptz := clock_timestamp();
  v_asset_id text;
  v_source_id text;
  v_reference_price numeric;
  v_observed_at timestamptz;
  v_captured_at timestamptz;
  v_evidence_sha256 text;
  v_evidence jsonb;
  existing public.big_move_reference_observations%rowtype;
begin
  if p_capture is null or octet_length(p_capture::text) > 200000 then
    raise exception 'invalid big-move reference capture';
  end if;

  v_asset_id := btrim(coalesce(p_capture ->> 'asset_id', ''));
  v_source_id := coalesce(p_capture ->> 'source_id', '');
  v_evidence_sha256 := lower(coalesce(p_capture ->> 'evidence_sha256', ''));
  v_evidence := p_capture -> 'evidence';

  begin
    v_reference_price := (p_capture ->> 'reference_price')::numeric;
    v_observed_at := (p_capture ->> 'observed_at')::timestamptz;
    v_captured_at := (p_capture ->> 'captured_at')::timestamptz;
  exception when others then
    raise exception 'invalid big-move reference capture fields';
  end;

  if v_asset_id = ''
     or v_source_id is distinct from 'TRUSTED_CROSS_VENUE_SPOT_REFERENCE_V1'
     or v_reference_price is null or v_reference_price <= 0
     or v_evidence_sha256 !~ '^[0-9a-f]{64}$'
     or v_evidence is null
     or v_evidence ->> 'schema' is distinct from 'trusted_cross_venue_reference_evidence.v1'
     or v_evidence ->> 'source_id' is distinct from v_source_id
     or v_evidence ->> 'asset_id' is distinct from v_asset_id
     or (v_evidence ->> 'reference_price')::numeric is distinct from v_reference_price
     or v_observed_at > v_captured_at
     or v_captured_at > v_now
     or v_captured_at < v_now - interval '5 minutes' then
    raise exception 'invalid big-move reference capture';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('big_move_reference_observations:' || v_evidence_sha256, 0)
  );

  select * into existing
    from public.big_move_reference_observations r
    where r.evidence_sha256 = v_evidence_sha256;
  if found then
    if existing.asset_id is distinct from v_asset_id
       or existing.source_id is distinct from v_source_id
       or existing.reference_price is distinct from v_reference_price
       or existing.observed_at is distinct from v_observed_at
       or existing.captured_at is distinct from v_captured_at
       or existing.evidence is distinct from v_evidence then
      raise exception 'immutable big-move reference observation conflict';
    end if;
    return query
      select existing.sequence,
             existing.asset_id,
             existing.reference_price,
             existing.observed_at,
             existing.captured_at,
             existing.created_at,
             existing.source_id,
             existing.evidence_sha256,
             existing.evidence;
    return;
  end if;

  return query
    insert into public.big_move_reference_observations(
      asset_id, source_id, reference_price, observed_at, captured_at,
      evidence_sha256, evidence, created_at
    ) values (
      v_asset_id, v_source_id, v_reference_price, v_observed_at, v_captured_at,
      v_evidence_sha256, v_evidence, v_now
    )
    returning big_move_reference_observations.sequence,
              big_move_reference_observations.asset_id,
              big_move_reference_observations.reference_price,
              big_move_reference_observations.observed_at,
              big_move_reference_observations.captured_at,
              big_move_reference_observations.created_at,
              big_move_reference_observations.source_id,
              big_move_reference_observations.evidence_sha256,
              big_move_reference_observations.evidence;
end;
$$;

revoke all on function public.append_big_move_reference_observation_v1(jsonb)
  from public, anon, authenticated;
grant execute on function public.append_big_move_reference_observation_v1(jsonb)
  to service_role;


create table if not exists public.big_move_forward_formations (
  sequence bigint generated always as identity primary key,
  forecast_fingerprint text not null unique
    check (forecast_fingerprint ~ '^[0-9a-f]{64}$'),
  reference_observation_sequence bigint not null
    references public.big_move_reference_observations(sequence),
  formation_payload jsonb not null,
  created_at timestamptz not null default clock_timestamp(),
  check (formation_payload ->> 'forecast_fingerprint' = forecast_fingerprint),
  check (formation_payload ->> 'schema' = 'forward_move_forecast.v1'),
  check (formation_payload ->> 'prospective_status' = 'UNTRUSTED_UNTIL_SERVER_RECEIPT'),
  check (formation_payload ? 'formed_at'),
  check (formation_payload ? 'evidence_cutoff'),
  check (formation_payload ? 'reference_price'),
  check (formation_payload ? 'reference_price_source_id'),
  check (formation_payload ? 'reference_price_observation_id'),
  check (formation_payload ? 'reference_price_observation_sha256'),
  check (formation_payload ? 'reference_price_observed_at'),
  check (
    (formation_payload ->> 'formed_at')::timestamptz <= created_at
    and (formation_payload ->> 'formed_at')::timestamptz >= created_at - interval '5 minutes'
  ),
  check (
    (formation_payload ->> 'reference_price_observed_at')::timestamptz <= created_at
    and (formation_payload ->> 'reference_price_observed_at')::timestamptz >= created_at - interval '5 minutes'
  ),
  check (
    (formation_payload ->> 'evidence_cutoff')::timestamptz
      <= (formation_payload ->> 'formed_at')::timestamptz
    and (formation_payload ->> 'reference_price_observed_at')::timestamptz
      <= (formation_payload ->> 'evidence_cutoff')::timestamptz
  ),
  check (octet_length(formation_payload::text) <= 200000)
);

comment on table public.big_move_forward_formations is
  'Append-only server-time receipts for research-only <=90d 2x+ forecast formation, each bound to a persisted reference observation. No trading or promotion authority.';

alter table public.big_move_forward_formations enable row level security;

revoke all on table public.big_move_forward_formations
  from public, anon, authenticated, service_role;
grant select on table public.big_move_forward_formations to service_role;

revoke all on sequence public.big_move_forward_formations_sequence_seq
  from public, anon, authenticated, service_role;
grant usage, select on sequence public.big_move_forward_formations_sequence_seq
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
declare
  v_now timestamptz := clock_timestamp();
  ref public.big_move_reference_observations%rowtype;
  existing public.big_move_forward_formations%rowtype;
begin
  if p_forecast_fingerprint is null
     or p_forecast_fingerprint !~ '^[0-9a-f]{64}$'
     or p_reference_observation_sequence is null
     or p_reference_observation_sequence <= 0
     or p_formation_payload is null
     or p_formation_payload ->> 'forecast_fingerprint' is distinct from p_forecast_fingerprint
     or p_formation_payload ->> 'schema' is distinct from 'forward_move_forecast.v1'
     or p_formation_payload ->> 'prospective_status' is distinct from 'UNTRUSTED_UNTIL_SERVER_RECEIPT'
     or octet_length(p_formation_payload::text) > 200000 then
    raise exception 'invalid big-move forward formation';
  end if;

  select * into ref
    from public.big_move_reference_observations r
    where r.sequence = p_reference_observation_sequence;
  if not found then
    raise exception 'missing durable big-move reference observation';
  end if;

  if ref.created_at > v_now
     or ref.created_at < v_now - interval '5 minutes'
     or p_formation_payload ->> 'asset_id' is distinct from ref.asset_id
     or p_formation_payload ->> 'reference_price_source_id' is distinct from ref.source_id
     or p_formation_payload ->> 'reference_price_observation_id'
          is distinct from ('big_move_reference:' || ref.sequence::text)
     or p_formation_payload ->> 'reference_price_observation_sha256'
          is distinct from ref.evidence_sha256
     or (p_formation_payload ->> 'reference_price')::numeric
          is distinct from ref.reference_price
     or (p_formation_payload ->> 'reference_price_observed_at')::timestamptz
          is distinct from ref.observed_at then
    raise exception 'formation does not match durable big-move reference observation';
  end if;

  begin
    if (p_formation_payload ->> 'formed_at')::timestamptz > v_now
       or (p_formation_payload ->> 'formed_at')::timestamptz < v_now - interval '5 minutes'
       or (p_formation_payload ->> 'reference_price_observed_at')::timestamptz > v_now
       or (p_formation_payload ->> 'reference_price_observed_at')::timestamptz < v_now - interval '5 minutes'
       or (p_formation_payload ->> 'evidence_cutoff')::timestamptz
            > (p_formation_payload ->> 'formed_at')::timestamptz
       or (p_formation_payload ->> 'reference_price_observed_at')::timestamptz
            > (p_formation_payload ->> 'evidence_cutoff')::timestamptz then
      raise exception 'stale or invalid big-move formation chronology';
    end if;
  exception when invalid_datetime_format then
    raise exception 'invalid big-move formation timestamps';
  end;

  perform pg_advisory_xact_lock(
    hashtextextended('big_move_forward_formations:' || p_forecast_fingerprint, 0)
  );

  select * into existing
    from public.big_move_forward_formations f
    where f.forecast_fingerprint = p_forecast_fingerprint;
  if found then
    if existing.formation_payload is distinct from p_formation_payload
       or existing.reference_observation_sequence is distinct from p_reference_observation_sequence then
      raise exception 'immutable big-move forward formation conflict';
    end if;
    return query
      select existing.sequence,
             existing.forecast_fingerprint,
             existing.reference_observation_sequence,
             ref.created_at,
             jsonb_build_object(
               'sequence', ref.sequence,
               'asset_id', ref.asset_id,
               'reference_price', ref.reference_price::text,
               'observed_at', to_char(ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'captured_at', to_char(ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
               'source_id', ref.source_id,
               'evidence_sha256', ref.evidence_sha256,
               'evidence', ref.evidence
             ),
             existing.created_at,
             existing.formation_payload;
    return;
  end if;

  return query
    insert into public.big_move_forward_formations(
      forecast_fingerprint, reference_observation_sequence, formation_payload, created_at
    ) values (
      p_forecast_fingerprint, p_reference_observation_sequence, p_formation_payload, v_now
    )
    returning big_move_forward_formations.sequence,
              big_move_forward_formations.forecast_fingerprint,
              big_move_forward_formations.reference_observation_sequence,
              ref.created_at,
              jsonb_build_object(
                'sequence', ref.sequence,
                'asset_id', ref.asset_id,
                'reference_price', ref.reference_price::text,
                'observed_at', to_char(ref.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'captured_at', to_char(ref.captured_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'source_id', ref.source_id,
                'evidence_sha256', ref.evidence_sha256,
                'evidence', ref.evidence
              ),
              big_move_forward_formations.created_at,
              big_move_forward_formations.formation_payload;
end;
$$;

revoke all on function public.append_big_move_forward_formation_v1(text, bigint, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_big_move_forward_formation_v1(text, bigint, jsonb)
  to service_role;

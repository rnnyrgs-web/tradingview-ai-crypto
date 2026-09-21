-- Research-only durable chronology for <=90d 2x+ forward forecasts.
--
-- Trusted prospectivity requires two server-controlled boundaries:
--   1) Postgres itself fetches contemporaneous public spot prices from two fixed
--      provider endpoints, parses them, and appends a reference-observation receipt;
--   2) forecast formation MUST consume that exact stored reference receipt.
--
-- Callers can choose only the Binance/OKX USDT instrument identifiers. They cannot
-- submit a price, timestamp, provider body, evidence digest, or created_at. Direct
-- table INSERT/UPDATE/DELETE is not granted to service_role. This is research-only
-- infrastructure and grants no prediction, promotion, broker or trade authority.

create schema if not exists extensions;
create extension if not exists http with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- Remove the earlier caller-payload overload if this migration is replayed against a
-- development database that briefly saw the pre-repair function.
drop function if exists public.append_big_move_reference_observation_v1(jsonb);

create table if not exists public.big_move_reference_observations (
  sequence bigint generated always as identity primary key,
  asset_id text not null check (length(btrim(asset_id)) > 0),
  source_id text not null
    check (source_id = 'TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2'),
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
  check (evidence ->> 'schema' = 'trusted_db_cross_venue_reference_evidence.v2'),
  check (evidence ->> 'source_id' = source_id),
  check (evidence ->> 'asset_id' = asset_id),
  check ((evidence ->> 'reference_price')::numeric = reference_price),
  check (octet_length(evidence::text) <= 250000)
);

comment on table public.big_move_reference_observations is
  'Append-only DB-fetched two-venue spot reference receipts for research-only <=90d 2x forecasts.';

alter table public.big_move_reference_observations enable row level security;

revoke all on table public.big_move_reference_observations
  from public, anon, authenticated, service_role;
grant select on table public.big_move_reference_observations to service_role;

revoke all on sequence public.big_move_reference_observations_sequence_seq
  from public, anon, authenticated, service_role;
grant usage, select on sequence public.big_move_reference_observations_sequence_seq
  to service_role;

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
declare
  v_now timestamptz := clock_timestamp();
  v_source_id constant text := 'TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2';
  v_binance_symbol text := upper(btrim(coalesce(p_binance_symbol, '')));
  v_okx_inst_id text := upper(btrim(coalesce(p_okx_inst_id, '')));
  v_base text;
  v_asset_id text;
  v_binance_status integer;
  v_okx_status integer;
  v_binance_content text;
  v_okx_content text;
  v_binance_payload jsonb;
  v_okx_payload jsonb;
  v_okx_row jsonb;
  v_binance_price numeric;
  v_okx_price numeric;
  v_binance_observed timestamptz;
  v_okx_observed timestamptz;
  v_observed_at timestamptz;
  v_reference_price numeric;
  v_deviation_bps numeric;
  v_binance_sha text;
  v_okx_sha text;
  v_capture_iso text;
  v_reference_text text;
  v_evidence_preimage text;
  v_evidence_sha text;
  v_evidence jsonb;
  existing public.big_move_reference_observations%rowtype;
begin
  -- Only USDT spot pairs are admitted in this first trusted reference contract.
  -- Fixed base URLs plus a strict symbol grammar prevent caller-controlled URLs/SSRF.
  if v_binance_symbol !~ '^[A-Z0-9]{2,24}USDT$'
     or v_okx_inst_id !~ '^[A-Z0-9]{2,24}-USDT$' then
    raise exception 'invalid trusted reference instruments';
  end if;
  v_base := substring(v_binance_symbol from '^([A-Z0-9]{2,24})USDT$');
  if v_base is null or v_okx_inst_id is distinct from (v_base || '-USDT') then
    raise exception 'cross-venue instrument identity mismatch';
  end if;
  v_asset_id := v_binance_symbol;

  begin
    select h.status, h.content
      into v_binance_status, v_binance_content
      from extensions.http_get(
        'https://data-api.binance.vision/api/v3/ticker/24hr?symbol=' || v_binance_symbol
      ) h;
    select h.status, h.content
      into v_okx_status, v_okx_content
      from extensions.http_get(
        'https://www.okx.com/api/v5/market/ticker?instId=' || v_okx_inst_id
      ) h;
  exception when others then
    raise exception 'trusted reference provider fetch failed';
  end;

  if v_binance_status is distinct from 200
     or v_okx_status is distinct from 200
     or v_binance_content is null
     or v_okx_content is null
     or octet_length(v_binance_content) > 100000
     or octet_length(v_okx_content) > 100000 then
    raise exception 'trusted reference provider response invalid';
  end if;

  begin
    v_binance_payload := v_binance_content::jsonb;
    v_okx_payload := v_okx_content::jsonb;
    if v_binance_payload ->> 'symbol' is distinct from v_binance_symbol then
      raise exception 'Binance symbol mismatch';
    end if;
    if v_okx_payload ->> 'code' is distinct from '0'
       or jsonb_typeof(v_okx_payload -> 'data') is distinct from 'array'
       or jsonb_array_length(v_okx_payload -> 'data') is distinct from 1 then
      raise exception 'OKX ticker response invalid';
    end if;
    v_okx_row := v_okx_payload -> 'data' -> 0;
    if v_okx_row ->> 'instId' is distinct from v_okx_inst_id then
      raise exception 'OKX instrument mismatch';
    end if;

    v_binance_price := (v_binance_payload ->> 'lastPrice')::numeric;
    v_okx_price := (v_okx_row ->> 'last')::numeric;
    v_binance_observed := to_timestamp((v_binance_payload ->> 'closeTime')::numeric / 1000.0);
    v_okx_observed := to_timestamp((v_okx_row ->> 'ts')::numeric / 1000.0);
  exception when others then
    raise exception 'trusted reference provider payload malformed';
  end;

  if v_binance_price <= 0 or v_okx_price <= 0
     or v_binance_observed > v_now or v_okx_observed > v_now
     or v_binance_observed < v_now - interval '120 seconds'
     or v_okx_observed < v_now - interval '120 seconds' then
    raise exception 'trusted reference provider value or timestamp invalid';
  end if;

  v_reference_price := (v_binance_price + v_okx_price) / 2;
  v_deviation_bps := abs(v_binance_price - v_okx_price)
    / v_reference_price * 10000;
  if v_deviation_bps > 75 then
    raise exception 'cross-venue reference prices disagree beyond frozen tolerance';
  end if;

  v_observed_at := greatest(v_binance_observed, v_okx_observed);
  v_binance_sha := encode(
    extensions.digest(convert_to(v_binance_content, 'UTF8'), 'sha256'), 'hex'
  );
  v_okx_sha := encode(
    extensions.digest(convert_to(v_okx_content, 'UTF8'), 'sha256'), 'hex'
  );
  v_capture_iso := to_char(
    v_now at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );
  v_reference_text := trim_scale(v_reference_price)::text;

  -- Deliberately simple cross-language fingerprint preimage. Python can reproduce
  -- this exactly without relying on PostgreSQL jsonb serialization order.
  v_evidence_preimage :=
      'trusted_db_cross_venue_reference.v2' || E'\n'
      || v_asset_id || E'\n'
      || v_binance_symbol || E'\n'
      || v_binance_sha || E'\n'
      || v_okx_inst_id || E'\n'
      || v_okx_sha || E'\n'
      || v_capture_iso || E'\n'
      || v_reference_text;
  v_evidence_sha := encode(
    extensions.digest(convert_to(v_evidence_preimage, 'UTF8'), 'sha256'), 'hex'
  );

  v_evidence := jsonb_build_object(
    'schema', 'trusted_db_cross_venue_reference_evidence.v2',
    'source_id', v_source_id,
    'asset_id', v_asset_id,
    'captured_at', v_capture_iso,
    'reference_price', v_reference_text,
    'cross_venue_deviation_bps', trim_scale(v_deviation_bps)::text,
    'derivation', jsonb_build_object(
      'method', 'ARITHMETIC_MIDPOINT_OF_DB_FETCHED_SPOT_LAST_PRICES',
      'version', '2',
      'max_provider_age_seconds', 120,
      'max_cross_venue_deviation_bps', '75',
      'provider_fetch_authority', 'POSTGRES_HTTP_EXTENSION_FIXED_ENDPOINTS'
    ),
    'providers', jsonb_build_array(
      jsonb_build_object(
        'venue', 'BINANCE_SPOT',
        'symbol', v_binance_symbol,
        'price', trim_scale(v_binance_price)::text,
        'observed_at', to_char(
          v_binance_observed at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        ),
        'raw_response_sha256', v_binance_sha,
        'raw_response_utf8', v_binance_content
      ),
      jsonb_build_object(
        'venue', 'OKX_SPOT',
        'symbol', v_okx_inst_id,
        'price', trim_scale(v_okx_price)::text,
        'observed_at', to_char(
          v_okx_observed at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        ),
        'raw_response_sha256', v_okx_sha,
        'raw_response_utf8', v_okx_content
      )
    )
  );

  perform pg_advisory_xact_lock(
    hashtextextended('big_move_reference_observations:' || v_evidence_sha, 0)
  );

  select * into existing
    from public.big_move_reference_observations r
    where r.evidence_sha256 = v_evidence_sha;
  if found then
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
      v_asset_id, v_source_id, v_reference_price, v_observed_at, v_now,
      v_evidence_sha, v_evidence, v_now
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

revoke all on function public.append_big_move_reference_observation_v1(text, text)
  from public, anon, authenticated;
grant execute on function public.append_big_move_reference_observation_v1(text, text)
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
  'Append-only server-time receipts for research-only <=90d 2x+ forecast formation, each bound to a DB-fetched two-venue reference observation.';

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

  if ref.source_id is distinct from 'TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2'
     or ref.created_at > v_now
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
       or (p_formation_payload ->> 'formed_at')::timestamptz < ref.created_at
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
               'reference_price', trim_scale(ref.reference_price)::text,
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
                'reference_price', trim_scale(ref.reference_price)::text,
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

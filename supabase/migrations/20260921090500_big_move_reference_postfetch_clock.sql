-- Runtime repair for <=90d 2x trusted reference capture.
--
-- The initial trusted-reference function sampled v_now before issuing the two
-- provider HTTP requests. A genuine provider response can therefore carry a
-- timestamp a few hundred milliseconds later than that pre-fetch clock and be
-- falsely rejected as "future". Capture/chronology time must be sampled only
-- after both server-controlled provider fetches complete.
--
-- This migration changes no provider, tolerance, age window, caller authority,
-- persistence authority, or trading/promotion authority. It only moves the
-- authoritative DB clock sample to the post-fetch boundary.

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
  v_now timestamptz;
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

  -- Critical chronology boundary: sample DB time only after both provider
  -- responses have been received. Provider timestamps are then compared to a
  -- clock that causally follows the fetch, rather than to a stale pre-fetch clock.
  v_now := clock_timestamp();

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
      v_evidence_sha, v_evidence, clock_timestamp()
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

create table if not exists public.big_move_forward_formations (
  sequence bigint generated always as identity primary key,
  forecast_fingerprint text not null unique
    check (forecast_fingerprint ~ '^[0-9a-f]{64}$'),
  formation_payload jsonb not null,
  created_at timestamptz not null default clock_timestamp(),
  check (formation_payload ->> 'forecast_fingerprint' = forecast_fingerprint),
  check (formation_payload ->> 'schema' = 'forward_move_forecast.v1'),
  check (formation_payload ->> 'prospective_status' = 'UNTRUSTED_UNTIL_SERVER_RECEIPT'),
  check (formation_payload ? 'formed_at'),
  check (formation_payload ? 'evidence_cutoff'),
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
  'Append-only trusted server-time receipts for research-only <=90d 2x+ forecast formation. No trading or promotion authority.';

alter table public.big_move_forward_formations enable row level security;

revoke all on table public.big_move_forward_formations
  from public, anon, authenticated, service_role;
grant select on table public.big_move_forward_formations to service_role;
grant insert (forecast_fingerprint, formation_payload)
  on table public.big_move_forward_formations to service_role;

revoke all on sequence public.big_move_forward_formations_sequence_seq
  from public, anon, authenticated, service_role;
grant usage, select on sequence public.big_move_forward_formations_sequence_seq
  to service_role;

create or replace function public.append_big_move_forward_formation_v1(
  p_forecast_fingerprint text,
  p_formation_payload jsonb
) returns table(
  sequence bigint,
  forecast_fingerprint text,
  created_at timestamptz,
  formation_payload jsonb
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  existing public.big_move_forward_formations%rowtype;
begin
  if p_forecast_fingerprint is null
     or p_forecast_fingerprint !~ '^[0-9a-f]{64}$'
     or p_formation_payload is null
     or p_formation_payload ->> 'forecast_fingerprint' is distinct from p_forecast_fingerprint
     or p_formation_payload ->> 'schema' is distinct from 'forward_move_forecast.v1'
     or p_formation_payload ->> 'prospective_status' is distinct from 'UNTRUSTED_UNTIL_SERVER_RECEIPT'
     or octet_length(p_formation_payload::text) > 200000 then
    raise exception 'invalid big-move forward formation';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('big_move_forward_formations:' || p_forecast_fingerprint, 0)
  );

  select * into existing
    from public.big_move_forward_formations
    where big_move_forward_formations.forecast_fingerprint = p_forecast_fingerprint;
  if found then
    if existing.formation_payload is distinct from p_formation_payload then
      raise exception 'immutable big-move forward formation conflict';
    end if;
    return query
      select existing.sequence,
             existing.forecast_fingerprint,
             existing.created_at,
             existing.formation_payload;
    return;
  end if;

  return query
    insert into public.big_move_forward_formations(
      forecast_fingerprint, formation_payload
    ) values (
      p_forecast_fingerprint, p_formation_payload
    )
    returning big_move_forward_formations.sequence,
              big_move_forward_formations.forecast_fingerprint,
              big_move_forward_formations.created_at,
              big_move_forward_formations.formation_payload;
end;
$$;

revoke all on function public.append_big_move_forward_formation_v1(text, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_big_move_forward_formation_v1(text, jsonb)
  to service_role;

create table if not exists public.money_intelligence_learning_events (
  sequence bigint generated always as identity primary key,
  event_id text not null unique,
  event_kind text not null check (event_kind in ('mechanism', 'evidence')),
  digest text not null check (digest ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (octet_length(payload::text) <= 4000000)
);

comment on table public.money_intelligence_learning_events is
  'Append-only point-in-time causal research memory. Service-role only; no trading or promotion authority.';

alter table public.money_intelligence_learning_events enable row level security;

revoke all on table public.money_intelligence_learning_events from public, anon, authenticated;
grant select, insert on table public.money_intelligence_learning_events to service_role;
revoke all on sequence public.money_intelligence_learning_events_sequence_seq from public, anon, authenticated;
grant usage, select on sequence public.money_intelligence_learning_events_sequence_seq to service_role;

create or replace function public.append_money_intelligence_learning_event(
  p_event_id text,
  p_event_kind text,
  p_digest text,
  p_payload jsonb,
  p_expected_count bigint,
  p_expected_sequence bigint
) returns text
language plpgsql
security invoker
set search_path = ''
as $$
declare
  existing record;
  actual_count bigint;
  actual_sequence bigint;
begin
  if p_event_id is null or length(p_event_id) = 0
     or p_event_kind not in ('mechanism', 'evidence')
     or p_digest !~ '^[0-9a-f]{64}$'
     or p_payload is null
     or octet_length(p_payload::text) > 4000000
     or p_expected_count is null or p_expected_count < 0
     or p_expected_sequence is null or p_expected_sequence < 0 then
    raise exception 'invalid money-intelligence event';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('money_intelligence_learning_events:append:v1', 0)
  );
  select event_kind, digest into existing
    from public.money_intelligence_learning_events
    where event_id = p_event_id;
  if found then
    if existing.event_kind <> p_event_kind or existing.digest <> p_digest then
      raise exception 'immutable money-intelligence event conflict';
    end if;
    return 'EXISTS';
  end if;

  select count(*), coalesce(max(sequence), 0)
    into actual_count, actual_sequence
    from public.money_intelligence_learning_events;
  if actual_count <> p_expected_count or actual_sequence <> p_expected_sequence then
    return 'STALE';
  end if;
  if actual_count >= 10000 then
    raise exception 'money-intelligence memory full';
  end if;
  insert into public.money_intelligence_learning_events(event_id, event_kind, digest, payload)
    values (p_event_id, p_event_kind, p_digest, p_payload);
  return 'APPENDED';
end;
$$;

revoke all on function public.append_money_intelligence_learning_event(
  text, text, text, jsonb, bigint, bigint
) from public, anon, authenticated;
grant execute on function public.append_money_intelligence_learning_event(
  text, text, text, jsonb, bigint, bigint
) to service_role;

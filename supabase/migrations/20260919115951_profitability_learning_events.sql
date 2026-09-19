create table if not exists public.profitability_learning_events (
  sequence bigint generated always as identity primary key,
  event_id text not null unique,
  event_kind text not null check (event_kind in ('experiment', 'proposal', 'legacy')),
  digest text not null check (digest ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (octet_length(payload::text) <= 16000000)
);

comment on table public.profitability_learning_events is
  'Append-only research memory. Service-role runtime only; no trading or promotion authority.';

alter table public.profitability_learning_events enable row level security;

revoke all on table public.profitability_learning_events from public, anon, authenticated;
grant select, insert on table public.profitability_learning_events to service_role;
revoke all on sequence public.profitability_learning_events_sequence_seq from public, anon, authenticated;
grant usage, select on sequence public.profitability_learning_events_sequence_seq to service_role;

create or replace function public.append_profitability_learning_event(
  p_event_id text,
  p_event_kind text,
  p_digest text,
  p_payload jsonb
) returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  existing record;
begin
  if p_event_id is null or length(p_event_id) = 0
     or p_event_kind not in ('experiment', 'proposal', 'legacy')
     or p_digest !~ '^[0-9a-f]{64}$'
     or p_payload is null
     or octet_length(p_payload::text) > 16000000 then
    raise exception 'invalid profitability-learning event';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_event_id, 0));
  select event_kind, digest into existing
    from public.profitability_learning_events
    where event_id = p_event_id;
  if found then
    if existing.event_kind <> p_event_kind or existing.digest <> p_digest then
      raise exception 'immutable profitability-learning event conflict';
    end if;
    return false;
  end if;
  if (select count(*) from public.profitability_learning_events) >= 10000 then
    raise exception 'profitability-learning memory full';
  end if;
  insert into public.profitability_learning_events(event_id, event_kind, digest, payload)
    values (p_event_id, p_event_kind, p_digest, p_payload);
  return true;
end;
$$;

revoke all on function public.append_profitability_learning_event(text, text, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_profitability_learning_event(text, text, text, jsonb)
  to service_role;

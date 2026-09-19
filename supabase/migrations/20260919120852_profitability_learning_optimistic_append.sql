create or replace function public.append_profitability_learning_event_v2(
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
     or p_event_kind not in ('experiment', 'proposal', 'legacy')
     or p_digest !~ '^[0-9a-f]{64}$'
     or p_payload is null
     or octet_length(p_payload::text) > 16000000
     or p_expected_count is null or p_expected_count < 0
     or p_expected_sequence is null or p_expected_sequence < 0 then
    raise exception 'invalid profitability-learning event';
  end if;

  -- One lock serializes the version check, capacity check, and append for all
  -- event IDs. Writers that classified against an older snapshot must retry.
  perform pg_advisory_xact_lock(
    hashtextextended('profitability_learning_events:append:v2', 0)
  );
  select event_kind, digest into existing
    from public.profitability_learning_events
    where event_id = p_event_id;
  if found then
    if existing.event_kind <> p_event_kind or existing.digest <> p_digest then
      raise exception 'immutable profitability-learning event conflict';
    end if;
    return 'EXISTS';
  end if;

  select count(*), coalesce(max(sequence), 0)
    into actual_count, actual_sequence
    from public.profitability_learning_events;
  if actual_count <> p_expected_count or actual_sequence <> p_expected_sequence then
    return 'STALE';
  end if;
  if actual_count >= 10000 then
    raise exception 'profitability-learning memory full';
  end if;
  insert into public.profitability_learning_events(event_id, event_kind, digest, payload)
    values (p_event_id, p_event_kind, p_digest, p_payload);
  return 'APPENDED';
end;
$$;

revoke all on function public.append_profitability_learning_event_v2(
  text, text, text, jsonb, bigint, bigint
) from public, anon, authenticated;
grant execute on function public.append_profitability_learning_event_v2(
  text, text, text, jsonb, bigint, bigint
) to service_role;

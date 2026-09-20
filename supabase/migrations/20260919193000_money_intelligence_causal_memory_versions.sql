create table if not exists public.money_intelligence_causal_memory_versions (
  sequence bigint generated always as identity primary key,
  content_digest text not null unique check (content_digest ~ '^[0-9a-f]{64}$'),
  parent_digest text check (parent_digest is null or parent_digest ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (payload ->> 'content_digest' = content_digest),
  check (octet_length(payload::text) <= 2000000)
);

comment on table public.money_intelligence_causal_memory_versions is
  'Append-only versioned causal-repricing research memory. Service-role runtime only; no trading or promotion authority.';

alter table public.money_intelligence_causal_memory_versions enable row level security;

revoke all on table public.money_intelligence_causal_memory_versions from public, anon, authenticated, service_role;
grant select, insert on table public.money_intelligence_causal_memory_versions to service_role;
revoke all on sequence public.money_intelligence_causal_memory_versions_sequence_seq from public, anon, authenticated, service_role;
grant usage, select on sequence public.money_intelligence_causal_memory_versions_sequence_seq to service_role;

create or replace function public.append_money_intelligence_causal_memory_version_v1(
  p_content_digest text,
  p_parent_digest text,
  p_payload jsonb,
  p_expected_sequence bigint,
  p_expected_digest text
) returns text
language plpgsql
security invoker
set search_path = ''
as $$
declare
  existing record;
  actual_sequence bigint;
  actual_digest text;
  actual_count bigint;
begin
  if p_content_digest is null or p_content_digest !~ '^[0-9a-f]{64}$'
     or (p_parent_digest is not null and p_parent_digest !~ '^[0-9a-f]{64}$')
     or p_payload is null
     or p_payload ->> 'content_digest' is distinct from p_content_digest
     or octet_length(p_payload::text) > 2000000
     or p_expected_sequence is null or p_expected_sequence < 0
     or (p_expected_digest is not null and p_expected_digest !~ '^[0-9a-f]{64}$') then
    raise exception 'invalid causal-memory version';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('money_intelligence_causal_memory_versions:append:v1', 0)
  );

  select parent_digest, payload into existing
    from public.money_intelligence_causal_memory_versions
    where content_digest = p_content_digest;
  if found then
    if existing.parent_digest is distinct from p_parent_digest
       or existing.payload is distinct from p_payload then
      raise exception 'immutable causal-memory version conflict';
    end if;
    return 'EXISTS';
  end if;

  select sequence, content_digest
    into actual_sequence, actual_digest
    from public.money_intelligence_causal_memory_versions
    order by sequence desc
    limit 1;
  actual_sequence := coalesce(actual_sequence, 0);

  if actual_sequence <> p_expected_sequence
     or actual_digest is distinct from p_expected_digest then
    return 'STALE';
  end if;
  if p_parent_digest is distinct from actual_digest then
    return 'STALE';
  end if;

  select count(*) into actual_count
    from public.money_intelligence_causal_memory_versions;
  if actual_count >= 512 then
    raise exception 'causal-memory version store full';
  end if;

  insert into public.money_intelligence_causal_memory_versions(
    content_digest, parent_digest, payload
  ) values (p_content_digest, p_parent_digest, p_payload);
  return 'APPENDED';
end;
$$;

revoke all on function public.append_money_intelligence_causal_memory_version_v1(
  text, text, jsonb, bigint, text
) from public, anon, authenticated;
grant execute on function public.append_money_intelligence_causal_memory_version_v1(
  text, text, jsonb, bigint, text
) to service_role;

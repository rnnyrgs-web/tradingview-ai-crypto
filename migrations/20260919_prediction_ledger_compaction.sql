-- Compact JSON-heavy resolved prediction history while preserving scientific evidence.
-- This migration intentionally keeps the newest 2,000 resolved calibration payloads
-- intact for bounded diagnostics and preserves point-in-time market/universe context
-- before clearing older verbose calibration JSON.

alter table public.prediction_ledger
  add column if not exists research_context jsonb;

create table if not exists public.prediction_universe_snapshots (
  scan_id uuid primary key,
  captured_at_text text,
  snapshot jsonb not null,
  archived_at timestamptz not null default now()
);

alter table public.prediction_universe_snapshots enable row level security;

insert into public.prediction_universe_snapshots (scan_id, captured_at_text, snapshot)
select distinct on (scan_id)
  scan_id,
  calibration->'preforecast_universe_snapshot'->>'captured_at',
  calibration->'preforecast_universe_snapshot'
from public.prediction_ledger
where scan_id is not null
  and calibration is not null
  and calibration ? 'preforecast_universe_snapshot'
  and jsonb_typeof(calibration->'preforecast_universe_snapshot') = 'object'
order by scan_id, id
on conflict (scan_id) do nothing;

update public.prediction_ledger
set research_context = jsonb_strip_nulls(
  jsonb_build_object(
    'preforecast_market_context', calibration->'preforecast_market_context',
    'action_diagnostics', calibration->'action_diagnostics',
    'source_system', calibration->'source_system',
    'shadow_only', calibration->'shadow_only'
  )
)
where resolved_at is not null
  and calibration is not null
  and (research_context is null or research_context = '{}'::jsonb);

with keep_recent as (
  select id
  from public.prediction_ledger
  where resolved_at is not null
  order by resolved_at desc, id desc
  limit 2000
)
update public.prediction_ledger
set calibration = null
where resolved_at is not null
  and calibration is not null
  and id not in (select id from keep_recent);

comment on column public.prediction_ledger.research_context is
  'Compact scientific provenance retained when verbose resolved calibration JSON is pruned.';

comment on table public.prediction_universe_snapshots is
  'Point-in-time preforecast universe snapshots archived before resolved calibration compaction; service-role research access only.';

-- The causal plan receipt uses the database-generated created_at timestamp.
-- Keep the existing invoker append RPC, but prevent the service role from
-- supplying a forged created_at through a direct table insert.
alter table public.money_intelligence_causal_memory_versions
  alter column created_at set default clock_timestamp();

revoke insert on table public.money_intelligence_causal_memory_versions
  from service_role;
grant insert (content_digest, parent_digest, payload)
  on table public.money_intelligence_causal_memory_versions
  to service_role;

-- Preserve the private read path used by the adapter and the append RPC.
grant select on table public.money_intelligence_causal_memory_versions
  to service_role;

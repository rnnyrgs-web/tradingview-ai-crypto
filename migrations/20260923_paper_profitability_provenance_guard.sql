-- Emergency fail-closed containment for #773.
--
-- The application currently computes paper profitability over the complete closed-trade
-- ledger even when strategy provenance is absent. Until the application can bind and
-- validate authentic provenance upstream, the account-level profitability flag must not
-- become true from unattributed trades. This guard intentionally does not certify that
-- non-empty provenance is authentic; it only prevents the known missing-provenance path
-- from creating a false profitability claim.

create or replace function public.guard_paper_profitability_provenance()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if coalesce(new.profitable_alert, false) then
    if not exists (
      select 1
      from public.paper_trades as t
      where t.account_id = new.id
        and upper(coalesce(t.status, '')) = 'CLOSED'
      group by t.account_id
      having count(*) >= 30
         and bool_and(nullif(btrim(t.signal_id), '') is not null)
         and bool_and(nullif(btrim(t.strategy_fingerprint), '') is not null)
         and bool_and(nullif(btrim(t.experiment_id), '') is not null)
         and bool_and(nullif(btrim(t.git_sha), '') is not null)
         and bool_and(nullif(btrim(t.dataset_sha256), '') is not null)
         and bool_and(nullif(btrim(t.strategy_contract_sha256), '') is not null)
    ) then
      new.profitable_alert := false;
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists paper_profitability_provenance_guard on public.paper_account;
create trigger paper_profitability_provenance_guard
before insert or update of profitable_alert on public.paper_account
for each row
execute function public.guard_paper_profitability_provenance();

comment on function public.guard_paper_profitability_provenance() is
  'Fail-closed #773 containment: paper_account.profitable_alert cannot become true while the closed-trade evidence set is under 30 rows or contains missing/blank strategy provenance.';

alter table public.paper_signal_decisions
    add column if not exists signal_id text,
    add column if not exists strategy_fingerprint text,
    add column if not exists experiment_id text,
    add column if not exists git_sha text,
    add column if not exists dataset_sha256 text,
    add column if not exists strategy_contract_sha256 text;

alter table public.paper_trades
    add column if not exists signal_id text,
    add column if not exists strategy_fingerprint text,
    add column if not exists experiment_id text,
    add column if not exists git_sha text,
    add column if not exists dataset_sha256 text,
    add column if not exists strategy_contract_sha256 text;

create or replace function public.enforce_paper_signal_decision_append_only()
returns trigger
language plpgsql
as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'paper_signal_decisions are append-only and cannot be deleted';
    end if;
    raise exception 'paper_signal_decisions are immutable after insert';
end;
$$;

drop trigger if exists paper_signal_decisions_append_only_guard on public.paper_signal_decisions;
create trigger paper_signal_decisions_append_only_guard
before update or delete on public.paper_signal_decisions
for each row execute function public.enforce_paper_signal_decision_append_only();

create or replace function public.enforce_paper_trade_strategy_provenance()
returns trigger
language plpgsql
as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'paper_trades are append-only and cannot be deleted';
    end if;
    if new.signal_id is distinct from old.signal_id
       or new.strategy_fingerprint is distinct from old.strategy_fingerprint
       or new.experiment_id is distinct from old.experiment_id
       or new.git_sha is distinct from old.git_sha
       or new.dataset_sha256 is distinct from old.dataset_sha256
       or new.strategy_contract_sha256 is distinct from old.strategy_contract_sha256
    then
        raise exception 'paper trade strategy provenance is immutable';
    end if;
    return new;
end;
$$;

drop trigger if exists paper_trades_strategy_provenance_guard on public.paper_trades;
create trigger paper_trades_strategy_provenance_guard
before update or delete on public.paper_trades
for each row execute function public.enforce_paper_trade_strategy_provenance();

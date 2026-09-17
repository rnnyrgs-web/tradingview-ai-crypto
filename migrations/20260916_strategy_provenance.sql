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
set search_path to 'public'
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

-- Extend the already-deployed paper trade append-only guard instead of stacking
-- a second UPDATE/DELETE trigger with partially overlapping semantics.
create or replace function public.enforce_paper_trade_append_only()
returns trigger
language plpgsql
set search_path to 'public'
as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'paper_trades are append-only and cannot be deleted';
    end if;

    if old.status = 'CLOSED' then
        raise exception 'closed paper_trades are immutable';
    end if;

    if new.account_id is distinct from old.account_id
       or new.signal_key is distinct from old.signal_key
       or new.scan_id is distinct from old.scan_id
       or new.symbol is distinct from old.symbol
       or new.horizon is distinct from old.horizon
       or new.direction is distinct from old.direction
       or new.entry_price is distinct from old.entry_price
       or new.stop_loss is distinct from old.stop_loss
       or new.target_price is distinct from old.target_price
       or new.quantity is distinct from old.quantity
       or new.notional_usd is distinct from old.notional_usd
       or new.risk_usd is distinct from old.risk_usd
       or new.fee_bps_one_way is distinct from old.fee_bps_one_way
       or new.evidence_score is distinct from old.evidence_score
       or new.research_only is distinct from old.research_only
       or new.opened_at is distinct from old.opened_at
       or new.created_at is distinct from old.created_at
       or new.signal_generated_at is distinct from old.signal_generated_at
       or new.decision_at is distinct from old.decision_at
       or new.entry_observed_market_price is distinct from old.entry_observed_market_price
       or new.entry_fill_observed_at is distinct from old.entry_fill_observed_at
       or new.entry_supported_notional is distinct from old.entry_supported_notional
       or new.entry_slippage_bps is distinct from old.entry_slippage_bps
       or new.entry_source_count is distinct from old.entry_source_count
       or new.execution_model_version is distinct from old.execution_model_version
       or new.signal_id is distinct from old.signal_id
       or new.strategy_fingerprint is distinct from old.strategy_fingerprint
       or new.experiment_id is distinct from old.experiment_id
       or new.git_sha is distinct from old.git_sha
       or new.dataset_sha256 is distinct from old.dataset_sha256
       or new.strategy_contract_sha256 is distinct from old.strategy_contract_sha256
    then
        raise exception 'paper trade entry identity/evidence/provenance is immutable';
    end if;

    if new.status <> 'CLOSED' then
        raise exception 'paper trade status may only transition OPEN to CLOSED';
    end if;
    if new.closed_at is null or new.exit_price is null or new.exit_reason is null or new.pnl_usd is null or new.pnl_pct is null then
        raise exception 'paper trade closure evidence is incomplete';
    end if;
    return new;
end;
$$;

-- Preserve the canonical existing trigger name and make sure no obsolete
-- parallel provenance trigger remains from an earlier migration attempt.
drop trigger if exists paper_trades_strategy_provenance_guard on public.paper_trades;
drop function if exists public.enforce_paper_trade_strategy_provenance();

drop trigger if exists paper_trades_append_only_guard on public.paper_trades;
create trigger paper_trades_append_only_guard
before update or delete on public.paper_trades
for each row execute function public.enforce_paper_trade_append_only();

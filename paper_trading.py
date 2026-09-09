import asyncio
import logging
import math
import threading
from datetime import datetime, timedelta, timezone

from paper_audit import V2_EXECUTION_MODEL, reconcile_paper_ledger
from paper_db import (
    close_paper_trade,
    fetch_all_paper_trades,
    fetch_latest_paper_reconciliation,
    fetch_open_paper_trades,
    fetch_paper_account,
    fetch_paper_trade_stats,
    fetch_ranked_opportunities,
    insert_paper_equity_snapshot,
    insert_paper_reconciliation_snapshot,
    insert_paper_signal_decision,
    insert_paper_trade,
    update_paper_account,
)
from execution_simulator import simulate_market_fill
from market_data import get_candles, get_order_book_intelligence
from production_risk_gate import assess_portfolio_risk
from utils import iso, now_utc

log = logging.getLogger(__name__)
ACCOUNT_ID = "default"
INITIAL_CASH = 100000.0
RISK_PER_TRADE_PCT = 0.50
MAX_OPEN_POSITIONS = 5
MAX_NOTIONAL_PCT = 20.0
FEE_BPS_ONE_WAY = 6.0
MIN_EVIDENCE_SCORE = 60.0
MAX_SIGNAL_AGE_SECONDS = 30 * 60
PAPER_INTERVAL_SECONDS = 15 * 60
_cycle_lock = threading.Lock()


def _last_price(symbol):
    """Return the latest observable market close used at this paper-cycle instant."""
    candles = get_candles(symbol, "15m", 3)
    if not candles:
        raise RuntimeError(f"No paper price for {symbol}")
    price = float(candles[-1]["close"])
    if not math.isfinite(price) or price <= 0:
        raise RuntimeError(f"Invalid paper price for {symbol}")
    return price


def _paper_fill_price(symbol, direction, requested_notional):
    """Create a size-aware forward-only fill from current independent order books."""
    market_price = _last_price(symbol)
    base = str(symbol).upper().split("-")[0]
    book = get_order_book_intelligence(base)
    simulation = simulate_market_fill(book, direction, requested_notional, FEE_BPS_ONE_WAY)
    if not simulation.executable or simulation.fill_price is None:
        raise RuntimeError(f"Execution evidence unavailable: {simulation.reason}")
    return market_price, float(simulation.fill_price), simulation


def _signal_key(row):
    return f"{row.get('scan_id')}:{row.get('horizon')}:{row.get('symbol')}:{row.get('direction')}"


def _mark_pnl(direction, entry, price, quantity):
    raw = (price - entry) * quantity
    return raw if direction == "LONG" else -raw


def _parse_utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _signal_freshness(row, now=None):
    generated = _parse_utc(row.get("generated_at"))
    current = now or now_utc()
    if generated is None:
        return False, "missing_signal_timestamp"
    age = (current - generated).total_seconds()
    if age < -5:
        return False, "future_signal_timestamp"
    if age > MAX_SIGNAL_AGE_SECONDS:
        return False, "stale_signal"
    return True, "fresh"


def _record_decision(row, decision, reason):
    direction = str(row.get("direction") or "").upper()
    symbol = str(row.get("symbol") or "").upper()
    horizon = str(row.get("horizon") or "")
    return insert_paper_signal_decision({
        "account_id": ACCOUNT_ID,
        "signal_key": _signal_key(row),
        "scan_id": row.get("scan_id"),
        "symbol": symbol or "UNKNOWN",
        "horizon": horizon or "UNKNOWN",
        "direction": direction or "UNKNOWN",
        "action": str(row.get("action") or "WAIT").upper(),
        "evidence_score": float(row.get("evidence_score") or 0),
        "decision": decision,
        "reason": reason,
        "signal_generated_at": row.get("generated_at"),
        "decided_at": iso(now_utc()),
    })


def _has_opposing_symbol_exposure(open_trades, symbol, direction):
    """Reject a new paper entry that would self-hedge the same asset."""
    symbol = str(symbol or "").upper()
    direction = str(direction or "").upper()
    if not symbol or direction not in {"LONG", "SHORT"}:
        return True
    for trade in open_trades or []:
        if str(trade.get("symbol") or "").upper() != symbol:
            continue
        existing_direction = str(trade.get("direction") or "").upper()
        if existing_direction in {"LONG", "SHORT"} and existing_direction != direction:
            return True
    return False


def _close_decision(trade, price):
    """Conservative stop/target trigger logic from observed forward prices."""
    stop = float(trade["stop_loss"])
    target = float(trade["target_price"])
    if trade["direction"] == "LONG":
        if price <= stop:
            return price, "STOP"
        if price >= target:
            return target, "TARGET"
    else:
        if price >= stop:
            return price, "STOP"
        if price <= target:
            return target, "TARGET"
    opened = _parse_utc(trade.get("opened_at"))
    if opened is None:
        log.warning("Invalid paper trade opened_at for id=%s", trade.get("id"))
    else:
        hours = 24 if trade["horizon"] == "24h" else 168
        if now_utc() >= opened + timedelta(hours=hours):
            return price, "TIME"
    return None, None


def _legacy_net_pnl(trade, exit_price):
    entry = float(trade["entry_price"])
    qty = float(trade["quantity"])
    gross = _mark_pnl(trade["direction"], entry, exit_price, qty)
    fees = exit_price * qty * float(trade["fee_bps_one_way"]) / 10000.0
    return gross - fees


def _v2_exit(trade, trigger_price, reason):
    quantity = float(trade["quantity"])
    requested_notional = max(float(trigger_price) * quantity, 1e-9)
    exit_side = "SHORT" if str(trade["direction"]).upper() == "LONG" else "LONG"
    observed_market, executable_fill, execution = _paper_fill_price(trade["symbol"], exit_side, requested_notional)
    final_fill = executable_fill
    if reason == "TARGET":
        target = float(trade["target_price"])
        fee = float(trade.get("fee_bps_one_way") or FEE_BPS_ONE_WAY) / 10000.0
        if str(trade["direction"]).upper() == "LONG":
            final_fill = min(final_fill, target * (1.0 - fee))
        else:
            final_fill = max(final_fill, target * (1.0 + fee))
    pnl = _mark_pnl(str(trade["direction"]).upper(), float(trade["entry_price"]), final_fill, quantity)
    audit = {
        "exit_trigger_observed_price": float(trigger_price),
        "exit_fill_observed_at": iso(now_utc()),
        "exit_supported_notional": execution.supported_notional,
        "exit_slippage_bps": execution.worst_slippage_bps,
        "exit_source_count": execution.source_count,
    }
    return observed_market, float(final_fill), float(pnl), audit


def _consistent(stats, max_drawdown_pct):
    return (
        stats["closed_trades"] >= 30
        and stats["net_pnl_usd"] > 0
        and stats["profit_factor"] >= 1.20
        and max_drawdown_pct <= 10.0
        and stats["last_20_pnl_usd"] > 0
    )


def _validate_persistent_account(account):
    if not account:
        raise RuntimeError("Paper account creation did not persist")
    initial_cash = float(account.get("initial_cash") or 0)
    if initial_cash != INITIAL_CASH:
        raise RuntimeError("Paper account initial_cash is immutable and must remain $100,000")
    for field in ("cash", "equity", "realized_pnl", "peak_equity", "max_drawdown_pct"):
        value = float(account.get(field))
        if not math.isfinite(value):
            raise RuntimeError(f"Paper account {field} must be finite")


def _marks_for_open_trades(open_trades):
    marks = {}
    for trade in open_trades:
        symbol = str(trade.get("symbol") or "").upper()
        if not symbol:
            raise RuntimeError("Open paper trade missing symbol")
        if symbol not in marks:
            marks[symbol] = _last_price(symbol)
    return marks


def run_paper_cycle():
    with _cycle_lock:
        return _run_paper_cycle_locked()


def _run_paper_cycle_locked():
    account = fetch_paper_account(ACCOUNT_ID)
    if not account:
        update_paper_account(ACCOUNT_ID, {
            "initial_cash": INITIAL_CASH,
            "cash": INITIAL_CASH,
            "equity": INITIAL_CASH,
            "realized_pnl": 0.0,
            "peak_equity": INITIAL_CASH,
            "max_drawdown_pct": 0.0,
            "profitable_alert": False,
        }, create=True)
        account = fetch_paper_account(ACCOUNT_ID)

    _validate_persistent_account(account)
    all_trades = fetch_all_paper_trades(ACCOUNT_ID)
    open_trades = [t for t in all_trades if str(t.get("status") or "").upper() == "OPEN"]

    # Acquire every mark before mutating the ledger. Missing current market data
    # aborts the cycle rather than silently marking a position back to entry.
    marks = _marks_for_open_trades(open_trades)
    ledger = reconcile_paper_ledger(account, all_trades, marks, INITIAL_CASH, compare_persisted=False)
    if not ledger.verified:
        insert_paper_reconciliation_snapshot(ACCOUNT_ID, ledger)
        raise RuntimeError("Paper ledger integrity failed before cycle")

    cash = float(ledger.expected_cash)
    realized = float(ledger.expected_realized_pnl)
    working_equity = float(ledger.expected_equity)

    for trade in list(open_trades):
        price = marks[str(trade["symbol"]).upper()]
        trigger_price, reason = _close_decision(trade, price)
        if trigger_price is None:
            continue
        audit = None
        if str(trade.get("execution_model_version") or "legacy_v1") == V2_EXECUTION_MODEL:
            try:
                _, exit_price, pnl, audit = _v2_exit(trade, trigger_price, reason)
            except Exception as exc:
                log.warning("Paper exit execution unavailable for %s: %s", trade.get("symbol"), str(exc)[:160])
                continue
        else:
            exit_price = float(trigger_price)
            pnl = _legacy_net_pnl(trade, exit_price)
        pnl_pct = pnl / float(trade["notional_usd"]) * 100.0 if float(trade["notional_usd"]) > 0 else 0.0
        if close_paper_trade(trade["id"], float(exit_price), reason, pnl, pnl_pct, audit=audit):
            cash += float(trade["notional_usd"]) + pnl
            realized += pnl

    open_trades = fetch_open_paper_trades(ACCOUNT_ID)
    open_pairs = {(t["symbol"], t["horizon"]) for t in open_trades}
    preopen_stats = fetch_paper_trade_stats(ACCOUNT_ID, INITIAL_CASH)
    risk_account = {**account, "cash": cash, "equity": working_equity, "realized_pnl": realized}
    portfolio_risk = assess_portfolio_risk(risk_account, open_trades, preopen_stats)
    candidates = []
    if portfolio_risk.blocked:
        log.warning("Global paper WAIT: %s", ",".join(portfolio_risk.reasons))
    else:
        for horizon in ("24h", "7d"):
            candidates.extend(fetch_ranked_opportunities(horizon=horizon, limit=20))
        candidates.sort(key=lambda r: float(r.get("evidence_score") or 0), reverse=True)

    for row in candidates:
        if len(open_trades) >= MAX_OPEN_POSITIONS:
            _record_decision(row, "REJECTED", "max_open_positions")
            continue
        direction = str(row.get("direction") or "").upper()
        symbol = str(row.get("symbol") or "").upper()
        horizon = str(row.get("horizon") or "")
        if direction not in {"LONG", "SHORT"} or horizon not in {"24h", "7d"} or not symbol:
            _record_decision(row, "REJECTED", "invalid_candidate_identity")
            continue
        if str(row.get("action") or "WAIT").upper() != "TRADE":
            _record_decision(row, "REJECTED", "not_actionable")
            continue
        fresh, freshness_reason = _signal_freshness(row)
        if not fresh:
            _record_decision(row, "REJECTED", freshness_reason)
            continue
        if float(row.get("evidence_score") or 0) < MIN_EVIDENCE_SCORE:
            _record_decision(row, "REJECTED", "below_paper_evidence_floor")
            continue
        if (symbol, horizon) in open_pairs:
            _record_decision(row, "REJECTED", "already_open_same_symbol_horizon")
            continue
        if _has_opposing_symbol_exposure(open_trades, symbol, direction):
            _record_decision(row, "REJECTED", "cross_horizon_symbol_conflict")
            continue

        signal_entry = float(row.get("entry_price") or 0)
        signal_stop = float(row.get("stop_loss") or 0)
        signal_target = float(row.get("target_1") or 0)
        if min(signal_entry, signal_stop, signal_target) <= 0:
            _record_decision(row, "REJECTED", "invalid_signal_prices")
            continue

        if direction == "LONG":
            stop_distance_pct = max(0.0, (signal_entry - signal_stop) / signal_entry)
            target_distance_pct = max(0.0, (signal_target - signal_entry) / signal_entry)
        else:
            stop_distance_pct = max(0.0, (signal_stop - signal_entry) / signal_entry)
            target_distance_pct = max(0.0, (signal_entry - signal_target) / signal_entry)
        if stop_distance_pct <= 0 or target_distance_pct <= 0:
            _record_decision(row, "REJECTED", "invalid_signal_geometry")
            continue

        equity_for_sizing = max(working_equity, 1.0)
        risk_usd = equity_for_sizing * RISK_PER_TRADE_PCT / 100.0
        max_notional = equity_for_sizing * MAX_NOTIONAL_PCT / 100.0
        desired_notional = min(risk_usd / stop_distance_pct, max_notional, cash)
        if desired_notional <= 0:
            _record_decision(row, "REJECTED", "insufficient_cash")
            continue

        try:
            observed_market, entry, execution = _paper_fill_price(symbol, direction, desired_notional)
        except Exception as exc:
            _record_decision(row, "REJECTED", "execution_evidence_unavailable")
            log.warning("Paper execution unavailable for %s: %s", symbol, str(exc)[:160])
            continue

        if direction == "LONG":
            stop = entry * (1.0 - stop_distance_pct)
            target = entry * (1.0 + target_distance_pct)
        else:
            stop = entry * (1.0 + stop_distance_pct)
            target = entry * (1.0 - target_distance_pct)
        risk_per_unit = abs(entry - stop)
        if min(entry, stop, target, risk_per_unit) <= 0:
            _record_decision(row, "REJECTED", "invalid_fill_geometry")
            continue

        quantity = min(risk_usd / risk_per_unit, desired_notional / entry, cash / entry)
        if quantity <= 0:
            _record_decision(row, "REJECTED", "invalid_quantity")
            continue
        notional = quantity * entry
        if notional > cash or (execution.supported_notional is not None and notional > execution.supported_notional + 1e-6):
            _record_decision(row, "REJECTED", "unsupported_notional")
            continue

        # First-seen decision is immutable. If this signal was already rejected in
        # an earlier cycle, the unique signal_key prevents it becoming a late fill.
        if not _record_decision(row, "ACCEPTED", "fresh_size_aware_forward_fill"):
            continue
        decision_at = iso(now_utc())
        if insert_paper_trade({
            "account_id": ACCOUNT_ID,
            "signal_key": _signal_key(row),
            "scan_id": row.get("scan_id"),
            "symbol": symbol,
            "horizon": horizon,
            "direction": direction,
            "status": "OPEN",
            "entry_price": entry,
            "stop_loss": stop,
            "target_price": target,
            "quantity": quantity,
            "notional_usd": notional,
            "risk_usd": risk_usd,
            "fee_bps_one_way": FEE_BPS_ONE_WAY,
            "evidence_score": float(row.get("evidence_score") or 0),
            "research_only": True,
            "signal_generated_at": row.get("generated_at"),
            "decision_at": decision_at,
            "entry_observed_market_price": observed_market,
            "entry_fill_observed_at": decision_at,
            "entry_supported_notional": execution.supported_notional,
            "entry_slippage_bps": execution.worst_slippage_bps,
            "entry_source_count": execution.source_count,
            "execution_model_version": V2_EXECUTION_MODEL,
        }):
            log.info(
                "Paper trade opened audited symbol=%s market=%s fill=%s notional=%.2f supported_tier=%s slippage_bps=%s sources=%s",
                symbol, observed_market, entry, notional, execution.supported_notional,
                execution.worst_slippage_bps, execution.source_count,
            )
            cash -= notional
            marks[symbol] = observed_market
            open_trades = fetch_open_paper_trades(ACCOUNT_ID)
            open_pairs.add((symbol, horizon))
            risk_account = {**risk_account, "cash": cash}
            portfolio_risk = assess_portfolio_risk(risk_account, open_trades, preopen_stats)
            if portfolio_risk.blocked:
                log.warning("Global paper WAIT after concentration change: %s", ",".join(portfolio_risk.reasons))
                break

    all_trades = fetch_all_paper_trades(ACCOUNT_ID)
    open_trades = [t for t in all_trades if str(t.get("status") or "").upper() == "OPEN"]
    # Every remaining open symbol must have a genuine current-cycle mark.
    for trade in open_trades:
        symbol = str(trade.get("symbol") or "").upper()
        if symbol not in marks:
            marks[symbol] = _last_price(symbol)

    derived = reconcile_paper_ledger(account, all_trades, marks, INITIAL_CASH, compare_persisted=False)
    if not derived.verified:
        insert_paper_reconciliation_snapshot(ACCOUNT_ID, derived)
        raise RuntimeError("Paper ledger integrity failed after cycle")

    equity = float(derived.expected_equity)
    cash = float(derived.expected_cash)
    realized = float(derived.expected_realized_pnl)
    peak = max(float(account.get("peak_equity") or INITIAL_CASH), equity)
    current_dd = max(0.0, (peak - equity) / peak * 100.0) if peak > 0 else 0.0
    max_dd = max(float(account.get("max_drawdown_pct") or 0), current_dd)
    stats = fetch_paper_trade_stats(ACCOUNT_ID, INITIAL_CASH)
    profitable = _consistent(stats, max(max_dd, stats["max_drawdown_pct"]))

    update_paper_account(ACCOUNT_ID, {
        "cash": cash,
        "equity": equity,
        "realized_pnl": realized,
        "peak_equity": peak,
        "max_drawdown_pct": max_dd,
        "profitable_alert": profitable,
    })
    refreshed = fetch_paper_account(ACCOUNT_ID)
    verified = reconcile_paper_ledger(refreshed, all_trades, marks, INITIAL_CASH, compare_persisted=True)
    insert_paper_reconciliation_snapshot(ACCOUNT_ID, verified)
    if not verified.verified:
        raise RuntimeError("Paper account failed independent post-write reconciliation")
    insert_paper_equity_snapshot(ACCOUNT_ID, equity, cash, len(open_trades), realized)
    return paper_status()


def paper_status():
    account = fetch_paper_account(ACCOUNT_ID)
    if not account:
        return {"configured": False, "research_only": True, "real_money": False, "trade_authority": False}
    stats = fetch_paper_trade_stats(ACCOUNT_ID, INITIAL_CASH)
    open_trades = fetch_open_paper_trades(ACCOUNT_ID)
    max_dd = max(float(account["max_drawdown_pct"]), stats["max_drawdown_pct"])
    portfolio_risk = assess_portfolio_risk(account, open_trades, stats)
    reconciliation = fetch_latest_paper_reconciliation(ACCOUNT_ID)
    return {
        "configured": True,
        "research_only": True,
        "real_money": False,
        "broker_connected": False,
        "trade_authority": False,
        "forward_fill_only": True,
        "size_aware_execution": True,
        "requires_two_reliable_books": True,
        "immutable_closed_trade_ledger": True,
        "decision_journal": True,
        "max_signal_age_seconds": MAX_SIGNAL_AGE_SECONDS,
        "starting_capital_usd": INITIAL_CASH,
        "equity_usd": round(float(account["equity"]), 2),
        "cash_usd": round(float(account["cash"]), 2),
        "realized_pnl_usd": round(float(account["realized_pnl"]), 2),
        "return_pct": round((float(account["equity"]) / INITIAL_CASH - 1.0) * 100.0, 3),
        "open_positions": len(open_trades),
        "closed_trades": stats["closed_trades"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "profit_factor": round(stats["profit_factor"], 3),
        "max_drawdown_pct": round(max_dd, 3),
        "last_20_pnl_usd": round(stats["last_20_pnl_usd"], 2),
        "consecutive_losses": int(stats.get("consecutive_losses") or 0),
        "global_risk_wait": portfolio_risk.blocked,
        "global_risk_reasons": list(portfolio_risk.reasons),
        "consistently_profitable": bool(account["profitable_alert"]),
        "profitability_rule": ">=30 closed trades, net P&L > 0, PF >= 1.20, max DD <= 10%, last 20 trades net positive",
        "reconciliation_verified": bool(reconciliation and reconciliation.get("verified")),
        "reconciliation_status": str((reconciliation or {}).get("status") or "NOT_YET_VERIFIED"),
        "reconciliation_checked_at": (reconciliation or {}).get("created_at"),
        "reconciliation_reasons": list((reconciliation or {}).get("reasons") or []),
    }


async def paper_trading_loop():
    while True:
        try:
            await asyncio.to_thread(run_paper_cycle)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("paper trading cycle failed: %s", type(exc).__name__)
        await asyncio.sleep(PAPER_INTERVAL_SECONDS)

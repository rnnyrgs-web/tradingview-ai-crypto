import asyncio
import logging
from datetime import datetime, timedelta

from paper_db import (
    close_paper_trade,
    fetch_open_paper_trades,
    fetch_paper_account,
    fetch_paper_trade_stats,
    fetch_ranked_opportunities,
    insert_paper_equity_snapshot,
    insert_paper_trade,
    update_paper_account,
)
from market_data import get_candles
from utils import now_utc

log = logging.getLogger(__name__)
ACCOUNT_ID = "default"
INITIAL_CASH = 100000.0
RISK_PER_TRADE_PCT = 0.50
MAX_OPEN_POSITIONS = 5
MAX_NOTIONAL_PCT = 20.0
FEE_BPS_ONE_WAY = 6.0
MIN_EVIDENCE_SCORE = 60.0
PAPER_INTERVAL_SECONDS = 15 * 60


def _last_price(symbol):
    candles = get_candles(symbol, "15m", 3)
    if not candles:
        raise RuntimeError(f"No paper price for {symbol}")
    return float(candles[-1]["close"])


def _signal_key(row):
    return f"{row.get('scan_id')}:{row.get('horizon')}:{row.get('symbol')}:{row.get('direction')}"


def _mark_pnl(direction, entry, price, quantity):
    raw = (price - entry) * quantity
    return raw if direction == "LONG" else -raw


def _close_decision(trade, price):
    stop = float(trade["stop_loss"])
    target = float(trade["target_price"])
    if trade["direction"] == "LONG":
        if price <= stop:
            return stop, "STOP"
        if price >= target:
            return target, "TARGET"
    else:
        if price >= stop:
            return stop, "STOP"
        if price <= target:
            return target, "TARGET"
    try:
        opened = datetime.fromisoformat(str(trade["opened_at"]).replace("Z", "+00:00"))
        hours = 24 if trade["horizon"] == "24h" else 168
        if now_utc() >= opened + timedelta(hours=hours):
            return price, "TIME"
    except Exception:
        pass
    return None, None


def _net_pnl(trade, exit_price):
    entry = float(trade["entry_price"])
    qty = float(trade["quantity"])
    gross = _mark_pnl(trade["direction"], entry, exit_price, qty)
    fees = (entry * qty + exit_price * qty) * float(trade["fee_bps_one_way"]) / 10000.0
    return gross - fees


def _consistent(stats, max_drawdown_pct):
    return (
        stats["closed_trades"] >= 30
        and stats["net_pnl_usd"] > 0
        and stats["profit_factor"] >= 1.20
        and max_drawdown_pct <= 10.0
        and stats["last_20_pnl_usd"] > 0
    )


def run_paper_cycle():
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

    cash = float(account["cash"])
    realized = float(account["realized_pnl"])

    for trade in fetch_open_paper_trades(ACCOUNT_ID):
        try:
            price = _last_price(trade["symbol"])
        except Exception:
            continue
        exit_price, reason = _close_decision(trade, price)
        if exit_price is None:
            continue
        pnl = _net_pnl(trade, float(exit_price))
        cash += float(trade["notional_usd"]) + pnl
        realized += pnl
        pnl_pct = pnl / float(trade["notional_usd"]) * 100.0 if float(trade["notional_usd"]) > 0 else 0.0
        close_paper_trade(trade["id"], float(exit_price), reason, pnl, pnl_pct)

    open_trades = fetch_open_paper_trades(ACCOUNT_ID)
    open_pairs = {(t["symbol"], t["horizon"]) for t in open_trades}
    candidates = []
    for horizon in ("24h", "7d"):
        candidates.extend(fetch_ranked_opportunities(horizon=horizon, limit=20))
    candidates.sort(key=lambda r: float(r.get("evidence_score") or 0), reverse=True)

    for row in candidates:
        if len(open_trades) >= MAX_OPEN_POSITIONS:
            break
        direction = str(row.get("direction") or "").upper()
        symbol = str(row.get("symbol") or "").upper()
        horizon = str(row.get("horizon") or "")
        if direction not in {"LONG", "SHORT"} or horizon not in {"24h", "7d"}:
            continue
        if float(row.get("evidence_score") or 0) < MIN_EVIDENCE_SCORE:
            continue
        if (symbol, horizon) in open_pairs:
            continue
        entry = float(row.get("entry_price") or 0)
        stop = float(row.get("stop_loss") or 0)
        target = float(row.get("target_1") or 0)
        risk_per_unit = abs(entry - stop)
        if min(entry, stop, target, risk_per_unit) <= 0:
            continue

        equity_for_sizing = max(float(account.get("equity") or INITIAL_CASH), 1.0)
        risk_usd = equity_for_sizing * RISK_PER_TRADE_PCT / 100.0
        max_notional = equity_for_sizing * MAX_NOTIONAL_PCT / 100.0
        quantity = min(risk_usd / risk_per_unit, max_notional / entry, cash / entry)
        if quantity <= 0:
            continue
        notional = quantity * entry
        entry_fee = notional * FEE_BPS_ONE_WAY / 10000.0
        if notional + entry_fee > cash:
            continue
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
        }):
            cash -= notional + entry_fee
            open_trades = fetch_open_paper_trades(ACCOUNT_ID)
            open_pairs.add((symbol, horizon))

    unrealized = 0.0
    held_notional = 0.0
    open_trades = fetch_open_paper_trades(ACCOUNT_ID)
    for trade in open_trades:
        held_notional += float(trade["notional_usd"])
        try:
            price = _last_price(trade["symbol"])
        except Exception:
            price = float(trade["entry_price"])
        unrealized += _mark_pnl(trade["direction"], float(trade["entry_price"]), price, float(trade["quantity"]))
    equity = cash + held_notional + unrealized
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
    insert_paper_equity_snapshot(ACCOUNT_ID, equity, cash, len(open_trades), realized)
    return paper_status()


def paper_status():
    account = fetch_paper_account(ACCOUNT_ID)
    if not account:
        return {"configured": False, "research_only": True, "real_money": False, "trade_authority": False}
    stats = fetch_paper_trade_stats(ACCOUNT_ID, INITIAL_CASH)
    max_dd = max(float(account["max_drawdown_pct"]), stats["max_drawdown_pct"])
    return {
        "configured": True,
        "research_only": True,
        "real_money": False,
        "broker_connected": False,
        "trade_authority": False,
        "starting_capital_usd": INITIAL_CASH,
        "equity_usd": round(float(account["equity"]), 2),
        "cash_usd": round(float(account["cash"]), 2),
        "realized_pnl_usd": round(float(account["realized_pnl"]), 2),
        "return_pct": round((float(account["equity"]) / INITIAL_CASH - 1.0) * 100.0, 3),
        "open_positions": len(fetch_open_paper_trades(ACCOUNT_ID)),
        "closed_trades": stats["closed_trades"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "profit_factor": round(stats["profit_factor"], 3),
        "max_drawdown_pct": round(max_dd, 3),
        "last_20_pnl_usd": round(stats["last_20_pnl_usd"], 2),
        "consistently_profitable": bool(account["profitable_alert"]),
        "profitability_rule": ">=30 closed trades, net P&L > 0, PF >= 1.20, max DD <= 10%, last 20 trades net positive",
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

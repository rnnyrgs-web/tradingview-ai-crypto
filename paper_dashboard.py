import html

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard import _authorized
from paper_db import fetch_all_paper_trades, fetch_open_paper_trades, fetch_paper_signal_decisions
from paper_trading import _liquidation_mark, paper_status


def _money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value):
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _live_position(trade):
    entry = float(trade.get("entry_price") or 0)
    qty = float(trade.get("quantity") or 0)
    notional = float(trade.get("notional_usd") or 0)
    direction = str(trade.get("direction") or "").upper()
    if entry <= 0 or qty <= 0:
        return {**trade, "last_price": None, "live_pnl": None, "live_pnl_pct": None}
    fill, execution = _liquidation_mark(trade)
    pnl = (fill - entry) * qty
    if direction == "SHORT":
        pnl = -pnl
    pct = pnl / notional * 100.0 if notional > 0 else 0.0
    return {
        **trade,
        "last_price": fill,
        "live_pnl": pnl,
        "live_pnl_pct": pct,
        "liquidation_source_count": execution.source_count,
        "liquidation_slippage_bps": execution.worst_slippage_bps,
    }


def _reconciled_totals(status, positions):
    initial = float(status.get("starting_capital_usd") or 100000.0)
    realized = float(status.get("realized_pnl_usd") or 0.0)
    if any(p.get("live_pnl") is None for p in positions):
        return initial, realized, None, None, None, False
    open_pnl = sum(float(p.get("live_pnl") or 0.0) for p in positions)
    total_pnl = realized + open_pnl
    equity = initial + total_pnl
    return initial, realized, open_pnl, total_pnl, equity, True


def paper_portfolio_page(request: Request):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    status = paper_status()
    positions = []
    for trade in fetch_open_paper_trades("default"):
        try:
            positions.append(_live_position(trade))
        except Exception:
            positions.append({**trade, "last_price": None, "live_pnl": None, "live_pnl_pct": None})

    rows = []
    for p in positions:
        pnl = p.get("live_pnl")
        cls = "gain" if pnl is not None and float(pnl) >= 0 else "loss"
        pnl_text = "P&L UNVERIFIED" if pnl is None else _money(pnl)
        pct_text = "" if pnl is None else _pct(p.get("live_pnl_pct"))
        liquidation = "—" if p.get("last_price") is None else p.get("last_price")
        rows.append(f"""
<tr><td><b>{html.escape(str(p.get('symbol') or ''))}</b></td>
<td>{html.escape(str(p.get('horizon') or ''))}</td><td>{html.escape(str(p.get('direction') or ''))}</td>
<td>{_money(p.get('notional_usd'))}</td><td>{p.get('entry_price')}</td>
<td>{liquidation}</td>
<td>{p.get('stop_loss')}</td><td>{p.get('target_price')}</td>
<td class="{cls}"><b>{pnl_text}</b><small>{pct_text}</small></td></tr>""")

    initial, realized, open_pnl, total_pnl, equity, live_marks_complete = _reconciled_totals(status, positions)
    total_cls = "gain" if total_pnl is not None and total_pnl >= 0 else "loss"
    open_cls = "gain" if open_pnl is not None and open_pnl >= 0 else "loss"
    return_pct = total_pnl / initial * 100.0 if total_pnl is not None and initial > 0 else None
    profitable = bool(status.get("consistently_profitable"))
    badge = "CONSISTENTLY PROFITABLE" if profitable else "TESTING — NOT PROVEN YET"
    badge_cls = "good" if profitable else "testing"
    verified = bool(status.get("reconciliation_verified"))
    verify_label = "LEDGER VERIFIED" if verified else html.escape(str(status.get("reconciliation_status") or "NOT VERIFIED"))
    verify_cls = "good" if verified else "bad"
    execution_status = html.escape(str(status.get("execution_authenticity_status") or "EXECUTION NOT VERIFIED"))
    execution_verified = bool(status.get("real_execution_verified"))
    execution_label = "REAL EXECUTION VERIFIED" if execution_verified else f"SIMULATION ONLY — {execution_status}"
    execution_cls = "good" if execution_verified else "bad"
    if not live_marks_complete:
        value_text = pnl_text = return_text = "P&L UNVERIFIED"
        open_text = "P&L UNVERIFIED"
    else:
        value_text = _money(equity)
        pnl_text = _money(total_pnl)
        return_text = _pct(return_pct)
        open_text = _money(open_pnl)

    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Paper Account {value_text}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#edf2f7;font-family:Arial,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:20px}}header{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}h1{{margin:0;font-size:26px}}a{{color:white;text-decoration:none;background:#26394c;padding:9px 12px;border-radius:8px}}.badge{{display:inline-block;margin:8px 6px 0 0;padding:6px 10px;border-radius:999px;font-weight:800;font-size:12px}}.good{{background:#123c2c;color:#9ee6c2}}.testing{{background:#403815;color:#eadb93}}.bad{{background:#4a2020;color:#ffb3b3}}.cards{{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:10px;margin:18px 0}}.card{{background:#101a25;border:1px solid #243548;border-radius:12px;padding:14px}}.card small{{display:block;color:#8296a9;margin-bottom:6px}}.card b{{font-size:21px}}.gain{{color:#8ee3b4}}.loss{{color:#ff9e9e}}table{{width:100%;border-collapse:collapse;background:#0d1721;border:1px solid #223246;border-radius:10px;overflow:hidden}}th,td{{padding:10px;border-bottom:1px solid #1c2b3b;text-align:left;white-space:nowrap}}th{{font-size:11px;color:#8195aa;background:#111d29}}td{{font-size:13px}}td small{{display:block;font-size:10px;margin-top:2px}}.note{{margin-top:14px;color:#91a4b7;font-size:12px;line-height:1.5}}@media(max-width:900px){{.cards{{grid-template-columns:repeat(2,1fr)}}.tablewrap{{overflow-x:auto}}}}
</style></head><body><div class="wrap"><header><div><h1>Current Account Value: {value_text}</h1><span class="badge {badge_cls}">{badge}</span><span class="badge {verify_cls}">{verify_label}</span><span class="badge {execution_cls}">{execution_label}</span></div><div><a href="/dashboard/paper/audit">Audit Trail</a> <a href="/dashboard">Signals</a></div></header>
<div class="cards">
<div class="card"><small>CURRENT ACCOUNT VALUE</small><b class="{total_cls}">{value_text}</b></div>
<div class="card"><small>ORIGINAL STARTING CAPITAL</small><b>{_money(initial)}</b></div>
<div class="card"><small>TOTAL P&L</small><b class="{total_cls}">{pnl_text}</b></div>
<div class="card"><small>RETURN</small><b class="{total_cls}">{return_text}</b></div>
<div class="card"><small>REALIZED P&L</small><b>{_money(realized)}</b></div>
<div class="card"><small>OPEN P&L — FULL LIQUIDATION</small><b class="{open_cls}">{open_text}</b></div>
<div class="card"><small>MAX DRAWDOWN</small><b>{float(status.get('max_drawdown_pct') or 0):.2f}%</b></div>
<div class="card"><small>OPEN POSITIONS</small><b>{int(status.get('open_positions') or 0)}</b></div>
<div class="card"><small>CLOSED TRADES</small><b>{int(status.get('closed_trades') or 0)}</b></div>
<div class="card"><small>WINS / LOSSES</small><b>{int(status.get('wins') or 0)} / {int(status.get('losses') or 0)}</b></div>
<div class="card"><small>PROFIT FACTOR</small><b>{float(status.get('profit_factor') or 0):.2f}</b></div>
<div class="card"><small>CASH</small><b>{_money(status.get('cash_usd'))}</b></div>
<div class="card"><small>STATUS</small><b>{'PASS' if profitable else 'COLLECTING DATA'}</b></div>
</div>
<h2>Open simulated positions</h2><div class="tablewrap"><table><thead><tr><th>CRYPTO</th><th>HORIZON</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>FULL LIQUIDATION FILL</th><th>STOP</th><th>TARGET</th><th>LIQUIDATION P&L</th></tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="9">No open paper positions right now.</td></tr>'}</tbody></table></div>
<div class="note"><b>Strict authenticity:</b> open P&L is marked to the currently executable full-position liquidation fill after visible-depth, spread/slippage and configured fee friction — never candle close or midpoint. Stops use intrabar high/low; if stop and target are both possible inside the same bar and ordering is unknowable, the stop is taken. Missing execution evidence shows <b>P&L UNVERIFIED</b> instead of reusing a stale value. New shorts are rejected until venue-specific carry/borrow/funding is verified. New entries are rejected until the configured fee schedule is explicitly verified. Historical legacy fills are never rewritten and therefore keep the simulation labelled as not real execution. No broker is connected and no real orders are placed.</div>
</div></body></html>""")


def paper_audit_page(request: Request):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    status = paper_status()
    trades = list(reversed(fetch_all_paper_trades("default")))[:200]
    decisions = fetch_paper_signal_decisions("default", limit=200)

    trade_rows = []
    for t in trades:
        trade_rows.append(
            "<tr>"
            f"<td>{html.escape(str(t.get('id') or ''))}</td>"
            f"<td>{html.escape(str(t.get('symbol') or ''))}</td>"
            f"<td>{html.escape(str(t.get('horizon') or ''))}</td>"
            f"<td>{html.escape(str(t.get('direction') or ''))}</td>"
            f"<td>{html.escape(str(t.get('status') or ''))}</td>"
            f"<td>{html.escape(str(t.get('signal_generated_at') or 'legacy'))}</td>"
            f"<td>{html.escape(str(t.get('entry_fill_observed_at') or t.get('opened_at') or ''))}</td>"
            f"<td>{html.escape(str(t.get('entry_price') or ''))}</td>"
            f"<td>{html.escape(str(t.get('entry_slippage_bps') or 'legacy'))}</td>"
            f"<td>{html.escape(str(t.get('exit_fill_observed_at') or t.get('closed_at') or '—'))}</td>"
            f"<td>{html.escape(str(t.get('exit_price') or '—'))}</td>"
            f"<td>{html.escape(str(t.get('exit_reason') or '—'))}</td>"
            f"<td>{_money(t.get('pnl_usd')) if t.get('pnl_usd') is not None else '—'}</td>"
            f"<td>{html.escape(str(t.get('execution_model_version') or 'legacy_v1'))}</td>"
            "</tr>"
        )

    decision_rows = []
    for d in decisions:
        decision_rows.append(
            "<tr>"
            f"<td>{html.escape(str(d.get('decided_at') or ''))}</td>"
            f"<td>{html.escape(str(d.get('symbol') or ''))}</td>"
            f"<td>{html.escape(str(d.get('horizon') or ''))}</td>"
            f"<td>{html.escape(str(d.get('direction') or ''))}</td>"
            f"<td>{html.escape(str(d.get('decision') or ''))}</td>"
            f"<td>{html.escape(str(d.get('reason') or ''))}</td>"
            f"<td>{html.escape(str(d.get('signal_generated_at') or ''))}</td>"
            "</tr>"
        )

    verified = bool(status.get("reconciliation_verified"))
    verify_label = "LEDGER VERIFIED" if verified else html.escape(str(status.get("reconciliation_status") or "NOT VERIFIED"))
    verify_cls = "good" if verified else "bad"
    execution_label = html.escape(str(status.get("execution_authenticity_status") or "EXECUTION NOT VERIFIED"))
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Paper Audit Trail</title><style>
body{{margin:0;background:#081018;color:#edf2f7;font-family:Arial,sans-serif}}.wrap{{max-width:1600px;margin:auto;padding:20px}}a{{color:white;text-decoration:none;background:#26394c;padding:9px 12px;border-radius:8px}}.badge{{display:inline-block;padding:6px 10px;border-radius:999px;font-weight:800;font-size:12px;margin-right:6px}}.good{{background:#123c2c;color:#9ee6c2}}.bad{{background:#4a2020;color:#ffb3b3}}.tablewrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:#0d1721;margin:12px 0 28px}}th,td{{padding:9px;border-bottom:1px solid #1c2b3b;text-align:left;white-space:nowrap;font-size:12px}}th{{color:#8195aa;background:#111d29}}p{{color:#91a4b7}}</style></head><body><div class="wrap"><div style="display:flex;justify-content:space-between;align-items:center"><div><h1>Paper Trading Audit Trail</h1><span class="badge {verify_cls}">{verify_label}</span><span class="badge bad">SIMULATION ONLY — {execution_label}</span></div><a href="/dashboard/paper">Back to Account</a></div>
<p>Last reconciliation: {html.escape(str(status.get('reconciliation_checked_at') or 'not yet'))}. Ledger verification means arithmetic/history integrity only; it is deliberately separate from real-execution verification. Legacy rows remain untouched and are never upgraded retroactively.</p>
<h2>Trade ledger</h2><div class="tablewrap"><table><thead><tr><th>ID</th><th>CRYPTO</th><th>HORIZON</th><th>SIDE</th><th>STATUS</th><th>SIGNAL TIME</th><th>ENTRY OBSERVED</th><th>ENTRY FILL</th><th>ENTRY SLIPPAGE BPS</th><th>EXIT OBSERVED</th><th>EXIT FILL</th><th>EXIT REASON</th><th>NET P&L</th><th>MODEL</th></tr></thead><tbody>{''.join(trade_rows) if trade_rows else '<tr><td colspan="14">No trades.</td></tr>'}</tbody></table></div>
<h2>First-seen signal decisions</h2><div class="tablewrap"><table><thead><tr><th>DECIDED</th><th>CRYPTO</th><th>HORIZON</th><th>SIDE</th><th>DECISION</th><th>REASON</th><th>SIGNAL GENERATED</th></tr></thead><tbody>{''.join(decision_rows) if decision_rows else '<tr><td colspan="7">No v2 decisions recorded yet.</td></tr>'}</tbody></table></div>
</div></body></html>""")

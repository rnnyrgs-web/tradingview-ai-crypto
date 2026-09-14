import html

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPPORTUNITY_HORIZONS
from dashboard import _authorized
from db import fetch_ranked_opportunities
from paper_db import fetch_all_paper_trades, fetch_open_paper_trades
from paper_trading import _liquidation_mark, paper_status


def _price(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:,.4f}"
    if x >= 0.01:
        return f"{x:.6f}"
    return f"{x:.8f}"


def _money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _signed_money(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{'+$' if x >= 0 else '-$'}{abs(x):,.2f}"


def _pct(entry, value):
    try:
        e = float(entry or 0)
        v = float(value or 0)
    except (TypeError, ValueError):
        return None
    if e <= 0 or v <= 0:
        return None
    return (v / e - 1.0) * 100.0


def _duration(row):
    horizon = str(row.get("timeframe") or row.get("horizon") or "").lower()
    return {
        "6h": "1–6 hours",
        "12h": "6–12 hours",
        "24h": "12–24 hours",
        "48h": "1–2 days",
        "72h": "2–3 days",
        "7d": "3–7 days",
    }.get(horizon, "Variable")


def _calibration(row):
    c = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(c, dict):
        return {"ready": False, "precision": None, "samples": 0, "minimum": 30, "raw": 0, "scope": "unknown"}
    try:
        samples = max(0, int(c.get("independent_samples") or c.get("samples") or 0))
    except (TypeError, ValueError):
        samples = 0
    try:
        minimum = max(1, int(c.get("minimum_samples") or 30))
    except (TypeError, ValueError):
        minimum = 30
    try:
        raw = max(0, int(c.get("raw_matching_rows") or 0))
    except (TypeError, ValueError):
        raw = 0
    ready = bool(c.get("ready"))
    try:
        precision = float(c.get("empirical_precision")) if ready and c.get("empirical_precision") is not None else None
    except (TypeError, ValueError):
        precision = None
    return {
        "ready": ready,
        "precision": precision,
        "samples": samples,
        "minimum": minimum,
        "raw": raw,
        "scope": str(c.get("scope") or "horizon_score_bin"),
    }


def _confidence(row):
    return _calibration(row)["precision"]


def _setup(row):
    raw = str(row.get("market_regime") or "Signal setup").strip()
    return raw.replace("_", " ").title() if raw else "Signal setup"


def _unified_rows(limit_per_horizon=20):
    rows = []
    for horizon in OPPORTUNITY_HORIZONS:
        rows.extend(fetch_ranked_opportunities(horizon=horizon, limit=limit_per_horizon))

    best = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        conf = _confidence(row) or 0.0
        move = abs(_pct(row.get("entry_price"), row.get("target_2")) or 0.0)
        score = (
            1 if str(row.get("action") or "").upper() == "TRADE" else 0,
            conf,
            float(row.get("evidence_score") or 0.0),
            move,
        )
        if symbol not in best or score > best[symbol][0]:
            best[symbol] = (score, row)

    result = [x[1] for x in best.values()]
    result.sort(
        key=lambda r: (
            0 if str(r.get("action") or "").upper() == "TRADE" else 1,
            -float(_confidence(r) or 0.0),
            -float(r.get("evidence_score") or 0.0),
            -abs(_pct(r.get("entry_price"), r.get("target_2")) or 0.0),
        )
    )
    return result


def _paper_snapshot():
    try:
        status = paper_status()
        open_trades = fetch_open_paper_trades("default")
        all_trades = fetch_all_paper_trades("default")
    except Exception:
        return {
            "available": False,
            "status": {},
            "positions": [],
            "closed": [],
            "open_pnl": None,
            "total_pnl": None,
            "equity": None,
            "win_rate": None,
        }

    positions = []
    marks_complete = True
    for trade in open_trades:
        row = dict(trade)
        try:
            entry = float(row.get("entry_price") or 0)
            qty = float(row.get("quantity") or 0)
            notional = float(row.get("notional_usd") or 0)
            direction = str(row.get("direction") or "").upper()
            fill, execution = _liquidation_mark(row)
            pnl = (float(fill) - entry) * qty
            if direction == "SHORT":
                pnl = -pnl
            pnl_pct = pnl / notional * 100.0 if notional > 0 else 0.0
            row.update({
                "last_price": float(fill),
                "live_pnl": pnl,
                "live_pnl_pct": pnl_pct,
                "mark_source_count": getattr(execution, "source_count", None),
            })
        except Exception:
            marks_complete = False
            row.update({"last_price": None, "live_pnl": None, "live_pnl_pct": None})
        positions.append(row)

    starting = float(status.get("starting_capital_usd") or 100000.0)
    realized = float(status.get("realized_pnl_usd") or 0.0)
    open_pnl = sum(float(p.get("live_pnl") or 0.0) for p in positions) if marks_complete else None
    total_pnl = realized + open_pnl if open_pnl is not None else None
    equity = starting + total_pnl if total_pnl is not None else None
    closed_trades = int(status.get("closed_trades") or 0)
    wins = int(status.get("wins") or 0)
    win_rate = (wins / closed_trades * 100.0) if closed_trades else None
    closed = [t for t in all_trades if str(t.get("status") or "").upper() == "CLOSED"]
    closed.sort(key=lambda t: str(t.get("closed_at") or ""), reverse=True)

    return {
        "available": True,
        "status": status,
        "positions": positions,
        "closed": closed[:10],
        "open_pnl": open_pnl,
        "total_pnl": total_pnl,
        "equity": equity,
        "win_rate": win_rate,
    }


def combined_dashboard_page(request: Request, horizon: str = "all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    rows = _unified_rows()
    paper = _paper_snapshot()
    pstatus = paper["status"]

    total = len(rows)
    strong_evidence = sum(1 for r in rows if float(r.get("evidence_score") or 0) >= 80)
    validated = sum(1 for r in rows if _confidence(r) is not None)
    strong_moves = sum(1 for r in rows if abs(_pct(r.get("entry_price"), r.get("target_2")) or 0) >= 100)
    actionable = sum(1 for r in rows if str(r.get("action") or "").upper() == "TRADE")
    evidence = (sum(float(r.get("evidence_score") or 0) for r in rows) / total) if total else 0

    body_rows = []
    for rank, row in enumerate(rows, 1):
        symbol = html.escape(str(row.get("symbol") or ""))
        direction = str(row.get("direction") or "").upper() or "WAIT"
        action = str(row.get("action") or "").upper()
        status = "ACTIVE" if action == "TRADE" else "WATCH"
        cal = _calibration(row)
        conf = cal["precision"]
        conf_text = f"{conf * 100:.0f}%" if conf is not None else "LEARNING"
        if conf is not None:
            validation_sub = f"N={cal['samples']} independent · raw={cal['raw']}"
        else:
            validation_sub = f"N={cal['samples']}/{cal['minimum']} independent · raw={cal['raw']}"
        progress = min(100.0, (cal["samples"] / cal["minimum"] * 100.0) if cal["minimum"] else 0.0)
        move = _pct(row.get("entry_price"), row.get("target_2"))
        move_text = f"{move:+.0f}%" if move is not None else "—"
        multiple = f"~{max(0, 1 + move / 100):.2f}×" if move is not None else ""
        side_class = "long" if direction == "LONG" else "short" if direction == "SHORT" else "wait"
        move_class = "up" if (move or 0) >= 0 else "down"
        rr = float(row.get("risk_reward") or 0)
        evidence_score = float(row.get("evidence_score") or 0)
        signal_id = int(row.get("id") or 0)
        setup = html.escape(_setup(row))
        search = html.escape(f"{symbol} {direction} {setup} {status}".lower())
        body_rows.append(f"""
        <tr class="signal-row" data-search="{search}" data-side="{direction.lower()}" data-status="{status.lower()}" data-confidence="{float(conf or 0):.6f}" data-evidence="{evidence_score:.2f}" data-move="{abs(float(move or 0)):.6f}" onclick="location.href='/dashboard/signal/{signal_id}'">
          <td class="rank">{rank}</td>
          <td><b>{symbol}</b></td>
          <td><span class="side {side_class}">{'↗' if direction == 'LONG' else '↘' if direction == 'SHORT' else '•'} {direction}</span></td>
          <td><b>{setup}</b><small>Evidence {evidence_score:.0f}/100</small></td>
          <td><div class="confidence">{conf_text}</div><small>{validation_sub}</small><div class="progress"><i style="width:{progress:.0f}%"></i></div></td>
          <td><div class="move {move_class}">{move_text}</div><small>{multiple}</small></td>
          <td><b>{html.escape(_duration(row))}</b></td>
          <td>{_price(row.get('entry_price'))}</td>
          <td class="target">{_price(row.get('target_2'))}</td>
          <td class="stop">{_price(row.get('stop_loss'))}</td>
          <td><b>{rr:.2f}</b></td>
          <td><span class="status {'active' if status == 'ACTIVE' else 'watch'}">{status}</span></td>
        </tr>""")

    table_body = "".join(body_rows) or '<tr><td colspan="12" class="empty">No current opportunities yet. The engine will not invent signals.</td></tr>'

    open_rows = []
    for p in paper["positions"]:
        pnl = p.get("live_pnl")
        pnl_cls = "gain" if pnl is not None and float(pnl) >= 0 else "loss"
        pnl_text = _signed_money(pnl) if pnl is not None else "UNVERIFIED"
        pct_text = f"{float(p.get('live_pnl_pct') or 0):+.2f}%" if pnl is not None else ""
        side = str(p.get("direction") or "").upper()
        side_cls = "long" if side == "LONG" else "short"
        open_rows.append(f"""
        <tr>
          <td><b>{html.escape(str(p.get('symbol') or ''))}</b></td>
          <td><span class="side {side_cls}">{side}</span></td>
          <td>{_money(p.get('notional_usd'))}</td>
          <td>{_price(p.get('entry_price'))}</td>
          <td>{_price(p.get('last_price'))}</td>
          <td class="{pnl_cls}"><b>{pnl_text}</b><small>{pct_text}</small></td>
          <td class="stop">{_price(p.get('stop_loss'))}</td>
          <td class="target">{_price(p.get('target_price'))}</td>
          <td>{html.escape(str(p.get('opened_at') or ''))}</td>
          <td><span class="status active">OPEN</span></td>
        </tr>""")
    open_table = "".join(open_rows) or '<tr><td colspan="10" class="empty">No open simulated trades right now.</td></tr>'

    closed_rows = []
    for t in paper["closed"]:
        pnl = t.get("pnl_usd")
        pnl_cls = "gain" if pnl is not None and float(pnl) >= 0 else "loss"
        side = str(t.get("direction") or "").upper()
        closed_rows.append(f"""
        <tr>
          <td><b>{html.escape(str(t.get('symbol') or ''))}</b></td>
          <td>{side}</td>
          <td>{_price(t.get('entry_price'))}</td>
          <td>{_price(t.get('exit_price'))}</td>
          <td>{html.escape(str(t.get('exit_reason') or '—'))}</td>
          <td class="{pnl_cls}"><b>{_signed_money(pnl)}</b></td>
          <td>{html.escape(str(t.get('closed_at') or ''))}</td>
        </tr>""")
    closed_table = "".join(closed_rows) or '<tr><td colspan="7" class="empty">No closed simulated trades yet.</td></tr>'

    total_pnl = paper["total_pnl"]
    total_pnl_cls = "gain" if total_pnl is not None and total_pnl >= 0 else "loss"
    open_pnl_cls = "gain" if paper["open_pnl"] is not None and paper["open_pnl"] >= 0 else "loss"
    win_rate = paper["win_rate"]
    win_rate_text = f"{win_rate:.1f}%" if win_rate is not None else "—"
    total_pnl_text = _signed_money(total_pnl) if total_pnl is not None else "UNVERIFIED"
    open_pnl_text = _signed_money(paper["open_pnl"]) if paper["open_pnl"] is not None else "UNVERIFIED"
    equity_text = _money(paper["equity"]) if paper["equity"] is not None else _money(pstatus.get("equity_usd"))

    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>Crypto Signals</title>
<style>
*{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--line:#173247;--muted:#7f9aaf;--text:#edf7ff;--blue:#2779ff;--green:#35dd91;--red:#ff6674;--amber:#f0c94f}}
body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740 0,#06111b 34%,#050d15 100%);color:var(--text);font-family:Inter,Arial,sans-serif;min-height:100vh}}
.shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}
.topbar{{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:14px}}.brand{{display:flex;align-items:center;gap:12px}}.logo{{font-size:30px;color:#2b9cff}}h1{{font-size:24px;margin:0}}.live{{font-size:12px;color:var(--green);font-weight:900;margin-left:6px}}.subtitle{{font-size:12px;color:#9bb0c1;margin-top:3px}}.search{{min-width:360px;max-width:520px;width:34%;background:#07131e;border:1px solid #1b3448;color:#fff;border-radius:10px;padding:12px 14px;outline:none}}
.cards{{display:grid;grid-template-columns:repeat(8,minmax(135px,1fr));gap:10px;margin-bottom:14px}}.card{{background:linear-gradient(180deg,#0b1b29,#091621);border:1px solid #19344a;border-radius:12px;padding:13px 14px}}.card .label{{font-size:10px;color:#8ca5b8;letter-spacing:.05em}}.card .value{{font-size:23px;font-weight:900;margin-top:6px}}.card .hint{{font-size:10px;color:#7892a6;margin-top:3px}}.gain{{color:var(--green)}}.loss{{color:var(--red)}}
.filters{{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}.filterset{{display:flex;gap:7px;flex-wrap:wrap}}button.filter,.paper{{background:#081520;color:#dce8f2;border:1px solid #25445b;border-radius:9px;padding:9px 13px;font-weight:800;cursor:pointer;text-decoration:none}}button.filter.active{{background:linear-gradient(180deg,#337fff,#2169eb);border-color:#4c91ff;color:white}}
.panel{{background:rgba(6,17,27,.86);border:1px solid #163247;border-radius:13px;padding:14px;box-shadow:0 20px 70px rgba(0,0,0,.2);margin-bottom:14px}}.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}}.panel-title{{font-size:20px;font-weight:900}}.scan{{font-size:11px;color:#91a8b9}}.scan b{{color:var(--green)}}
.tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1250px;background:#07131e}}thead{{position:sticky;top:0;background:#0b1b28;z-index:2}}th{{text-align:left;color:#829db2;font-size:10px;letter-spacing:.055em;padding:11px 10px;border-bottom:1px solid #1b3a51}}td{{padding:11px 10px;border-bottom:1px solid #10283a;font-size:12px;vertical-align:middle;white-space:nowrap}}tbody tr{{cursor:pointer}}tbody tr:hover{{background:#0c1d2a}}.rank{{color:#5e7b91;width:36px}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}.side{{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:6px 9px;font-weight:900;font-size:11px}}.side.long{{background:#0c3527;color:#4de3a0}}.side.short{{background:#3a1720;color:#ff7c87}}.side.wait{{background:#3a3515;color:#ead76e}}.confidence,.move{{font-size:14px;font-weight:900}}.move.up{{color:var(--green)}}.move.down{{color:var(--red)}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.status{{display:inline-block;border-radius:7px;padding:6px 9px;font-size:10px;font-weight:900}}.status.active{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.progress{{width:92px;height:4px;background:#13283a;border-radius:999px;margin-top:5px;overflow:hidden}}.progress i{{display:block;height:100%;background:#35dd91;border-radius:999px}}.empty{{padding:30px;color:#9db0bf;text-align:center}}.note{{font-size:11px;color:#7f9aaf;line-height:1.45;margin:9px 2px 0}}.foot{{display:flex;justify-content:space-between;color:#668296;font-size:10px;margin-top:10px;gap:16px;flex-wrap:wrap}}
@media(max-width:1350px){{.cards{{grid-template-columns:repeat(4,1fr)}}}}@media(max-width:800px){{.shell{{padding:12px}}.topbar{{align-items:flex-start;flex-direction:column}}.search{{width:100%;min-width:0}}.cards{{grid-template-columns:repeat(2,1fr)}}.card .value{{font-size:21px}}}}
</style></head><body><div class="shell">
<div class="topbar"><div class="brand"><div class="logo">▥</div><div><h1>Crypto Signals <span class="live">● LIVE</span></h1><div class="subtitle">Unified research signals + live paper-trading ledger · 24/7 · refreshes every 60s</div></div></div><input id="search" class="search" placeholder="Search any coin (e.g. BTC, XRP, PONS...)" autocomplete="off"></div>

<div class="cards">
<div class="card"><div class="label">CANDIDATES</div><div class="value">{total}</div><div class="hint">current ranked opportunities</div></div>
<div class="card"><div class="label">STRONG EVIDENCE</div><div class="value">{strong_evidence}</div><div class="hint">evidence ≥80/100</div></div>
<div class="card"><div class="label">VALIDATED SIGNALS</div><div class="value">{validated}</div><div class="hint">forward calibration ready</div></div>
<div class="card"><div class="label">OPEN TRADES</div><div class="value">{int(pstatus.get('open_positions') or len(paper['positions']))}</div><div class="hint">paper positions now</div></div>
<div class="card"><div class="label">TOTAL P&L</div><div class="value {total_pnl_cls}">{total_pnl_text}</div><div class="hint">realized + executable open P&L</div></div>
<div class="card"><div class="label">OPEN P&L</div><div class="value {open_pnl_cls}">{open_pnl_text}</div><div class="hint">full-liquidation mark</div></div>
<div class="card"><div class="label">WIN RATE</div><div class="value">{win_rate_text}</div><div class="hint">{int(pstatus.get('wins') or 0)}W / {int(pstatus.get('losses') or 0)}L</div></div>
<div class="card"><div class="label">PROFIT FACTOR</div><div class="value">{float(pstatus.get('profit_factor') or 0):.2f}</div><div class="hint">max DD {float(pstatus.get('max_drawdown_pct') or 0):.2f}%</div></div>
</div>

<div class="panel">
<div class="panel-head"><div class="panel-title">System Trades & P&L <span class="live">● PAPER LIVE</span></div><div class="scan">Account value <b>{equity_text}</b> · Realized P&L {_signed_money(pstatus.get('realized_pnl_usd'))} · Cash {_money(pstatus.get('cash_usd'))}</div></div>
<div class="tablewrap"><table><thead><tr><th>ASSET</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>LIVE EXIT MARK</th><th>OPEN P&L</th><th>STOP</th><th>TARGET</th><th>OPENED</th><th>STATUS</th></tr></thead><tbody>{open_table}</tbody></table></div>
<div class="note">These are the system's actual simulated paper positions. P&L uses the currently executable full-position liquidation fill after spread/slippage/fee friction where available. No real broker is connected and no real-money orders are being placed.</div>
</div>

<div class="filters"><div class="filterset"><button class="filter active" data-filter="all">✧ All Signals</button><button class="filter" data-filter="evidence">★ Strong Evidence</button><button class="filter" data-filter="validated">✓ Validated</button><button class="filter" data-filter="strong">🚀 2×+ Moves</button><button class="filter" data-filter="active">◉ Actionable</button><button class="filter" data-filter="bull">↗ Top Bullish</button><button class="filter" data-filter="bear">↘ Top Bearish</button></div><a class="paper" href="/dashboard/paper">Full Paper Account</a></div>

<div class="panel"><div class="panel-head"><div class="panel-title">Live Crypto Signals</div><div class="scan"><b>●</b> scanning all internal timeframes · one strongest opportunity per asset · refresh 60s</div></div>
<div class="tablewrap"><table><thead><tr><th>#</th><th>ASSET</th><th>DIRECTION</th><th>SETUP</th><th>VALIDATION</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>STOP</th><th>R:R</th><th>STATUS</th></tr></thead><tbody id="signals">{table_body}</tbody></table></div>
<div class="note"><b>Why N can stay low:</b> N counts only non-overlapping, full-horizon, resolved forward outcomes inside the same horizon + evidence-score calibration bucket. It does not count repeated 15-minute scans. “raw=” shows how many resolved matching rows existed before the independence filter, so you can see that the system is collecting data without pretending correlated scans are independent proof.</div>
</div>

<div class="panel"><div class="panel-head"><div class="panel-title">Recent Closed Trades</div><div class="scan">Closed trades {int(pstatus.get('closed_trades') or 0)} · 2×+ opportunities {strong_moves} · actionable production signals {actionable} · avg evidence {evidence:.0f}/100</div></div>
<div class="tablewrap"><table><thead><tr><th>ASSET</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>EXIT REASON</th><th>REALIZED P&L</th><th>CLOSED</th></tr></thead><tbody>{closed_table}</tbody></table></div></div>

<div class="foot"><span>Crypto Signals · unified opportunities + authentic paper ledger</span><span>Internal fixed horizons remain research/calibration inputs; user-facing signals show estimated duration instead.</span></div>
</div>
<script>
const rows=[...document.querySelectorAll('.signal-row')];
const buttons=[...document.querySelectorAll('button.filter')];
const search=document.getElementById('search');
let mode='all';
function apply(){{
 const q=(search.value||'').trim().toLowerCase();
 rows.forEach(r=>{{
   const ev=parseFloat(r.dataset.evidence||'0'), conf=parseFloat(r.dataset.confidence||'0'), mv=parseFloat(r.dataset.move||'0');
   let ok=mode==='all'||(mode==='evidence'&&ev>=80)||(mode==='validated'&&conf>0)||(mode==='strong'&&mv>=100)||(mode==='active'&&r.dataset.status==='active')||(mode==='bull'&&r.dataset.side==='long')||(mode==='bear'&&r.dataset.side==='short');
   if(q && !(r.dataset.search||'').includes(q)) ok=false;
   r.style.display=ok?'':'none';
 }});
}}
buttons.forEach(b=>b.addEventListener('click',()=>{{buttons.forEach(x=>x.classList.remove('active'));b.classList.add('active');mode=b.dataset.filter;apply();}}));
search.addEventListener('input',apply);
</script></body></html>""")

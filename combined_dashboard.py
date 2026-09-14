import html

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPPORTUNITY_HORIZONS
from dashboard import _authorized
from db import fetch_ranked_opportunities


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


def _confidence(row):
    c = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(c, dict) or not c.get("ready"):
        return None
    try:
        return float(c.get("empirical_precision"))
    except (TypeError, ValueError):
        return None


def _setup(row):
    raw = str(row.get("market_regime") or "Signal setup").strip()
    return raw.replace("_", " ").title() if raw else "Signal setup"


def _unified_rows(limit_per_horizon=25):
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


def combined_dashboard_page(request: Request, horizon: str = "all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    rows = _unified_rows()
    total = len(rows)
    high = sum(1 for r in rows if (_confidence(r) or 0) >= 0.65)
    strong = sum(1 for r in rows if abs(_pct(r.get("entry_price"), r.get("target_2")) or 0) >= 100)
    active = sum(1 for r in rows if str(r.get("action") or "").upper() == "TRADE")
    evidence = (sum(float(r.get("evidence_score") or 0) for r in rows) / total) if total else 0

    body_rows = []
    for rank, row in enumerate(rows, 1):
        symbol = html.escape(str(row.get("symbol") or ""))
        direction = str(row.get("direction") or "").upper() or "WAIT"
        action = str(row.get("action") or "").upper()
        status = "ACTIVE" if action == "TRADE" else "WATCH"
        conf = _confidence(row)
        conf_text = f"{conf * 100:.0f}%" if conf is not None else "LEARNING"
        move = _pct(row.get("entry_price"), row.get("target_2"))
        move_text = f"{move:+.0f}%" if move is not None else "—"
        multiple = f"~{max(0, 1 + move / 100):.2f}×" if move is not None else ""
        side_class = "long" if direction == "LONG" else "short" if direction == "SHORT" else "wait"
        move_class = "up" if (move or 0) >= 0 else "down"
        rr = float(row.get("risk_reward") or 0)
        signal_id = int(row.get("id") or 0)
        setup = html.escape(_setup(row))
        search = html.escape(f"{symbol} {direction} {setup} {status}".lower())
        body_rows.append(f"""
        <tr class="signal-row" data-search="{search}" data-side="{direction.lower()}" data-status="{status.lower()}" data-confidence="{float(conf or 0):.6f}" data-move="{abs(float(move or 0)):.6f}" onclick="location.href='/dashboard/signal/{signal_id}'">
          <td class="rank">{rank}</td>
          <td><b>{symbol}</b></td>
          <td><span class="side {side_class}">{'↗' if direction == 'LONG' else '↘' if direction == 'SHORT' else '•'} {direction}</span></td>
          <td><b>{setup}</b><small>Evidence {float(row.get('evidence_score') or 0):.0f}/100</small></td>
          <td><div class="confidence">{conf_text}</div><small>{'forward verified' if conf is not None else 'forward learning'}</small></td>
          <td><div class="move {move_class}">{move_text}</div><small>{multiple}</small></td>
          <td><b>{html.escape(_duration(row))}</b></td>
          <td>{_price(row.get('entry_price'))}</td>
          <td class="target">{_price(row.get('target_2'))}</td>
          <td class="stop">{_price(row.get('stop_loss'))}</td>
          <td><b>{rr:.2f}</b></td>
          <td><span class="status {'active' if status == 'ACTIVE' else 'watch'}">{status}</span></td>
        </tr>""")

    table_body = "".join(body_rows) or '<tr><td colspan="12" class="empty">No current opportunities yet. The engine will not invent signals.</td></tr>'

    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>Crypto Signals</title>
<style>
*{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--line:#173247;--muted:#7f9aaf;--text:#edf7ff;--blue:#2779ff;--green:#35dd91;--red:#ff6674;--amber:#f0c94f}}
body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740 0,#06111b 34%,#050d15 100%);color:var(--text);font-family:Inter,Arial,sans-serif;min-height:100vh}}
.shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}
.topbar{{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:14px}}.brand{{display:flex;align-items:center;gap:12px}}.logo{{font-size:30px;color:#2b9cff}}h1{{font-size:24px;margin:0}}.live{{font-size:12px;color:var(--green);font-weight:900;margin-left:6px}}.subtitle{{font-size:12px;color:#9bb0c1;margin-top:3px}}.search{{min-width:360px;max-width:520px;width:34%;background:#07131e;border:1px solid #1b3448;color:#fff;border-radius:10px;padding:12px 14px;outline:none}}
.cards{{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:10px;margin-bottom:14px}}.card{{background:linear-gradient(180deg,#0b1b29,#091621);border:1px solid #19344a;border-radius:12px;padding:14px 16px}}.card .label{{font-size:10px;color:#8ca5b8;letter-spacing:.05em}}.card .value{{font-size:27px;font-weight:900;margin-top:6px}}.card .hint{{font-size:10px;color:#7892a6;margin-top:3px}}
.filters{{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}.filterset{{display:flex;gap:7px;flex-wrap:wrap}}button.filter,.paper{{background:#081520;color:#dce8f2;border:1px solid #25445b;border-radius:9px;padding:9px 13px;font-weight:800;cursor:pointer;text-decoration:none}}button.filter.active{{background:linear-gradient(180deg,#337fff,#2169eb);border-color:#4c91ff;color:white}}
.panel{{background:rgba(6,17,27,.86);border:1px solid #163247;border-radius:13px;padding:14px;box-shadow:0 20px 70px rgba(0,0,0,.2)}}.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}}.panel-title{{font-size:21px;font-weight:900}}.scan{{font-size:11px;color:#91a8b9}}.scan b{{color:var(--green)}}
.tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1450px;background:#07131e}}thead{{position:sticky;top:0;background:#0b1b28;z-index:2}}th{{text-align:left;color:#829db2;font-size:10px;letter-spacing:.055em;padding:11px 10px;border-bottom:1px solid #1b3a51}}td{{padding:11px 10px;border-bottom:1px solid #10283a;font-size:12px;vertical-align:middle;white-space:nowrap}}tbody tr{{cursor:pointer}}tbody tr:hover{{background:#0c1d2a}}.rank{{color:#5e7b91;width:36px}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}.side{{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:6px 9px;font-weight:900;font-size:11px}}.side.long{{background:#0c3527;color:#4de3a0}}.side.short{{background:#3a1720;color:#ff7c87}}.side.wait{{background:#3a3515;color:#ead76e}}.confidence,.move{{font-size:14px;font-weight:900}}.move.up{{color:var(--green)}}.move.down{{color:var(--red)}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.status{{display:inline-block;border-radius:7px;padding:6px 9px;font-size:10px;font-weight:900}}.status.active{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.empty{{padding:30px;color:#9db0bf;text-align:center}}.foot{{display:flex;justify-content:space-between;color:#668296;font-size:10px;margin-top:10px;gap:16px;flex-wrap:wrap}}
@media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.search{{min-width:260px;width:45%}}}}@media(max-width:700px){{.shell{{padding:12px}}.topbar{{align-items:flex-start;flex-direction:column}}.search{{width:100%;min-width:0}}.cards{{grid-template-columns:repeat(2,1fr)}}.card .value{{font-size:22px}}}}
</style></head><body><div class="shell">
<div class="topbar"><div class="brand"><div class="logo">▥</div><div><h1>Crypto Signals <span class="live">● LIVE</span></h1><div class="subtitle">Multi-timeframe · AI research · unified opportunities · 24/7</div></div></div><input id="search" class="search" placeholder="Search any coin (e.g. BTC, XRP, PONS...)" autocomplete="off"></div>
<div class="cards">
<div class="card"><div class="label">TOTAL OPPORTUNITIES</div><div class="value">{total}</div><div class="hint">current unified signals</div></div>
<div class="card"><div class="label">HIGH CONFIDENCE</div><div class="value">{high}</div><div class="hint">verified ≥65%</div></div>
<div class="card"><div class="label">STRONG MOVES</div><div class="value">{strong}</div><div class="hint">2×+ potential</div></div>
<div class="card"><div class="label">TRADE SETUPS</div><div class="value">{active}</div><div class="hint">currently actionable</div></div>
<div class="card"><div class="label">AVG EVIDENCE</div><div class="value">{evidence:.0f}</div><div class="hint">signal strength / 100</div></div>
<div class="card"><div class="label">REFRESH</div><div class="value">60s</div><div class="hint">automatic update</div></div>
</div>
<div class="filters"><div class="filterset"><button class="filter active" data-filter="all">✧ All Signals</button><button class="filter" data-filter="high">★ High Confidence</button><button class="filter" data-filter="strong">🚀 Strong Moves (2×+)</button><button class="filter" data-filter="active">◉ Trade Setups</button><button class="filter" data-filter="long">↗ Top Bullish</button><button class="filter" data-filter="short">↘ Top Bearish</button></div><a class="paper" href="/dashboard/paper">Paper Account</a></div>
<div class="panel"><div class="panel-head"><div class="panel-title">Live Crypto Signals</div><div class="scan"><b>●</b> Scanning all internal timeframes · one strongest opportunity per asset · refreshes every 60s</div></div>
<div class="tablewrap"><table><thead><tr><th>#</th><th>ASSET</th><th>DIRECTION</th><th>SETUP</th><th>CONFIDENCE</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>STOP</th><th>R:R</th><th>STATUS</th></tr></thead><tbody>{table_body}</tbody></table></div>
<div class="foot"><span>No fixed 6h / 12h / 24h / 48h / 72h / 7d tabs. The board shows the expected duration directly.</span><span>Confidence appears only when genuine forward calibration is ready.</span></div></div>
</div><script>
const rows=[...document.querySelectorAll('.signal-row')];const buttons=[...document.querySelectorAll('.filter')];const search=document.getElementById('search');let active='all';
function apply(){{const q=(search.value||'').trim().toLowerCase();rows.forEach(r=>{{const ms=!q||r.dataset.search.includes(q);let mf=true;if(active==='high')mf=parseFloat(r.dataset.confidence)>=.65;if(active==='strong')mf=parseFloat(r.dataset.move)>=100;if(active==='active')mf=r.dataset.status==='active';if(active==='long')mf=r.dataset.side==='long';if(active==='short')mf=r.dataset.side==='short';r.style.display=(ms&&mf)?'':'none';}})}}
buttons.forEach(b=>b.addEventListener('click',()=>{{active=b.dataset.filter;buttons.forEach(x=>x.classList.toggle('active',x===b));apply();}}));search.addEventListener('input',apply);
</script></body></html>""")

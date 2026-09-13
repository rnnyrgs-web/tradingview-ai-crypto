import base64
import hashlib
import hmac
import html
import time

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from config import DASHBOARD_SECRET, OPPORTUNITY_HORIZONS
from db import fetch_ranked_opportunities, fetch_signal_by_id
from market_data import get_candles

SESSION_COOKIE = "crypto_dashboard_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
DASHBOARD_HORIZONS = OPPORTUNITY_HORIZONS
PERSISTED_SIGNAL_HORIZONS = DASHBOARD_HORIZONS


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _session_token(expires: int) -> str:
    msg = str(expires).encode("ascii")
    sig = hmac.new(DASHBOARD_SECRET.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{expires}.{_b64(sig)}"


def _valid_session(token: str) -> bool:
    if not DASHBOARD_SECRET or not token or "." not in token:
        return False
    try:
        exp_s, supplied_sig = token.split(".", 1)
        exp = int(exp_s)
    except (ValueError, TypeError):
        return False
    if exp < int(time.time()):
        return False
    expected = _session_token(exp).split(".", 1)[1]
    return hmac.compare_digest(expected, supplied_sig)


def _authorized(request: Request):
    return _valid_session(request.cookies.get(SESSION_COOKIE, ""))


def _price(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:,.4f}"
    if x >= 0.01:
        return f"{x:.6f}"
    return f"{x:.8f}"


def _entry_zone(row):
    entry = float(row.get("entry_price") or 0)
    stop = float(row.get("stop_loss") or 0)
    risk = abs(entry - stop)
    if entry <= 0 or risk <= 0:
        return entry, entry
    pad = risk * 0.10
    return entry - pad, entry + pad


def _trade_label(row):
    action = str(row.get("action") or "WAIT").upper()
    direction = str(row.get("direction") or "").upper()
    if action != "TRADE":
        return "WAIT"
    return "LONG" if direction == "LONG" else "SHORT"


def _signed_pct(row, field):
    try:
        entry = float(row.get("entry_price") or 0)
        value = float(row.get(field) or 0)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or value <= 0:
        return None
    return (value / entry - 1.0) * 100.0


def _pct_text(value):
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def _duration(row):
    """Internal research horizon. Kept for data access, never exposed as dashboard buckets."""
    raw = str(row.get("timeframe") or row.get("horizon") or "24h").strip().lower()
    return raw if raw in DASHBOARD_HORIZONS else "24h"


def _estimated_duration(row):
    return {
        "6h": "1–6 hours",
        "12h": "6–12 hours",
        "24h": "12–24 hours",
        "48h": "1–2 days",
        "72h": "2–3 days",
        "7d": "3–7 days",
    }.get(_duration(row), "Variable")


def _calibration_metrics(row):
    """Expose only genuine empirical forward calibration; never synthesize accuracy."""
    calibration = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(calibration, dict):
        return {"accuracy":"LEARNING","floor":"—","n":"N=0/30","samples":0,"minimum_samples":30,"ready":False,"precision":None}
    try:
        samples=max(0,int(calibration.get("independent_samples") or calibration.get("samples") or 0))
    except (TypeError,ValueError):
        samples=0
    try:
        minimum=max(1,int(calibration.get("minimum_samples") or 30))
    except (TypeError,ValueError):
        minimum=30
    ready=bool(calibration.get("ready"))
    precision=calibration.get("empirical_precision") if ready else None
    floor=calibration.get("precision_95pct_lower") if ready else None
    try:
        precision_value=float(precision) if precision is not None else None
        accuracy_text=f"{precision_value*100.0:.0f}%" if precision_value is not None else "LEARNING"
    except (TypeError,ValueError):
        precision_value=None
        accuracy_text="LEARNING"
    try:
        floor_text=f"{float(floor)*100.0:.0f}%" if floor is not None else "—"
    except (TypeError,ValueError):
        floor_text="—"
    return {
        "accuracy":accuracy_text,
        "floor":floor_text,
        "n":f"N={samples}" if ready else f"N={samples}/{minimum}",
        "samples":samples,
        "minimum_samples":minimum,
        "ready":ready,
        "precision":precision_value,
    }


def _expected_move(row):
    return _signed_pct(row, "target_2")


def _move_multiple(move_pct):
    if move_pct is None:
        return ""
    multiple = max(0.0, 1.0 + (move_pct / 100.0))
    return f"~{multiple:.2f}×"


def _setup_text(row):
    regime = str(row.get("market_regime") or "Signal setup").strip()
    return regime.replace("_", " ").title() if regime else "Signal setup"


def _rows_for_dashboard(limit_per_horizon=20):
    """Combine every internal horizon, then show one strongest current opportunity per asset."""
    rows = []
    for horizon in PERSISTED_SIGNAL_HORIZONS:
        for row in fetch_ranked_opportunities(horizon=horizon, limit=limit_per_horizon):
            rows.append(row)

    best_by_symbol = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        calibration = _calibration_metrics(row)
        move = _expected_move(row)
        score = (
            1 if str(row.get("action") or "").upper() == "TRADE" else 0,
            1 if calibration["ready"] else 0,
            float(calibration["precision"] or 0.0),
            float(row.get("evidence_score") or 0.0),
            abs(float(move or 0.0)),
        )
        current = best_by_symbol.get(symbol)
        if current is None or score > current[0]:
            best_by_symbol[symbol] = (score, row)

    result = [item[1] for item in best_by_symbol.values()]
    result.sort(
        key=lambda row: (
            0 if str(row.get("action") or "").upper() == "TRADE" else 1,
            -float((_calibration_metrics(row).get("precision") or 0.0)),
            -float(row.get("evidence_score") or 0.0),
            -abs(float(_expected_move(row) or 0.0)),
        )
    )
    return result


def login_page(error=""):
    if not DASHBOARD_SECRET:
        error="Dashboard authentication is not configured yet. Set DASHBOARD_SECRET privately in Render before using this page."
    err=f'<div class="error">{html.escape(error)}</div>' if error else ""
    disabled=" disabled" if not DASHBOARD_SECRET else ""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crypto Signal Dashboard</title><style>body{{font-family:Arial,sans-serif;background:#06111b;color:#edf7ff;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}.box{{width:min(440px,90vw);background:#0b1824;border:1px solid #1b3143;border-radius:16px;padding:28px;box-shadow:0 24px 70px rgba(0,0,0,.4)}}input,button{{box-sizing:border-box;width:100%;padding:13px;border-radius:10px;border:1px solid #29445b;font-size:16px}}input{{background:#07111b;color:white;margin:12px 0}}button{{background:#2679ff;color:white;font-weight:bold;cursor:pointer}}button:disabled{{opacity:.45;cursor:not-allowed}}small{{color:#87a0b5}}.error{{background:#4a1c1c;padding:10px;border-radius:8px;margin:10px 0}}</style></head><body><div class="box"><h2>Crypto Signal Dashboard</h2><p>Private unified signal dashboard across any expected move duration.</p>{err}<form method="post" action="/dashboard/login"><input name="secret" type="password" autocomplete="current-password" placeholder="Private dashboard password" required{disabled}><button{disabled}>Unlock dashboard</button></form><p><small>The password is submitted only to your Render service over HTTPS and replaced by a signed HttpOnly session cookie.</small></p></div></body></html>""")


async def handle_login(request: Request):
    if not DASHBOARD_SECRET:
        return login_page()
    raw=(await request.body()).decode("utf-8",errors="replace")
    form=__import__("urllib.parse",fromlist=["parse_qs"]).parse_qs(raw,keep_blank_values=True)
    supplied=(form.get("secret") or [""])[0]
    if not hmac.compare_digest(supplied,DASHBOARD_SECRET):
        return login_page("Incorrect password.")
    expires=int(time.time())+SESSION_TTL_SECONDS
    response=RedirectResponse("/dashboard",status_code=303)
    response.set_cookie(SESSION_COOKIE,_session_token(expires),max_age=SESSION_TTL_SECONDS,httponly=True,secure=True,samesite="strict",path="/dashboard")
    return response


def dashboard_page(request: Request,horizon="all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login",status_code=303)

    rows=_rows_for_dashboard(limit_per_horizon=20)
    table_rows=[]
    high_confidence=0
    strong_moves=0
    trade_setups=0
    evidence_values=[]

    for rank,row in enumerate(rows,1):
        lo,hi=_entry_zone(row)
        label=_trade_label(row)
        direction=str(row.get("direction") or "").upper()
        score=float(row.get("evidence_score") or 0)
        evidence_values.append(score)
        rr=float(row.get("risk_reward") or 0)
        calibration=_calibration_metrics(row)
        if calibration["ready"] and float(calibration["precision"] or 0) >= .65:
            high_confidence += 1
        move=_expected_move(row)
        if move is not None and abs(move) >= 100:
            strong_moves += 1
        if str(row.get("action") or "").upper() == "TRADE":
            trade_setups += 1

        stop_pct=_signed_pct(row,"stop_loss")
        symbol=html.escape(str(row.get("symbol") or ""))
        signal_id=int(row.get("id") or 0)
        detail=f"/dashboard/signal/{signal_id}"
        confidence_text=calibration["accuracy"]
        confidence_sub=calibration["n"] if calibration["ready"] else "forward learning"
        confidence_class="confidence ready" if calibration["ready"] else "confidence learning"
        move_class="up" if (move or 0) >= 0 else "down"
        side_class="long" if direction == "LONG" else "short" if direction == "SHORT" else "wait"
        status="ACTIVE" if label in {"LONG","SHORT"} else "WATCH"
        status_class="active" if status == "ACTIVE" else "watch"
        setup=html.escape(_setup_text(row))
        search_blob=html.escape(f"{symbol} {direction} {setup} {status}".lower())
        data_conf=float(calibration["precision"] or 0)
        data-move = abs(float(move or 0.0))

        table_rows.append(f"""<tr class="signal-row" data-search="{search_blob}" data-side="{direction.lower()}" data-status="{status.lower()}" data-confidence="{data_conf:.6f}" data-move="{data-move:.6f}" onclick="location.href='{detail}'">
            <td class="rank">{rank}</td>
            <td><div class="asset">{symbol}</div></td>
            <td><span class="side {side_class}">{'↗' if direction=='LONG' else '↘' if direction=='SHORT' else '•'} {direction or 'WAIT'}</span></td>
            <td><div class="setup">{setup}</div><small>Evidence {score:.0f}/100</small></td>
            <td><div class="{confidence_class}">{confidence_text}</div><small>{confidence_sub}</small></td>
            <td><div class="move {move_class}">{_pct_text(move)}</div><small>{_move_multiple(move)}</small></td>
            <td><div class="duration-text">{html.escape(_estimated_duration(row))}</div></td>
            <td class="num">{_price(lo)}–{_price(hi)}</td>
            <td class="num target">{_price(row.get('target_2'))}</td>
            <td class="num stop">{_price(row.get('stop_loss'))}<small>{_pct_text(stop_pct)}</small></td>
            <td class="num rr">{rr:.2f}</td>
            <td><span class="status {status_class}">{status}</span></td>
            <td><a class="chart" href="{detail}">VIEW CHART</a></td>
        </tr>""")

    avg_evidence=(sum(evidence_values)/len(evidence_values)) if evidence_values else 0
    empty="" if table_rows else '<div class="empty">No current opportunities yet. The engine will not invent signals to fill the board.</div>'
    table="" if not table_rows else f"""<div class="tablewrap"><table><thead><tr><th>#</th><th>ASSET</th><th>DIRECTION</th><th>SETUP</th><th>CONFIDENCE</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>STOP</th><th>R:R</th><th>STATUS</th><th>CHART</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>"""

    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>Crypto Signals</title><style>
    *{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--panel2:#0c1d2b;--line:#183247;--muted:#7f9aaf;--text:#edf7ff;--blue:#2779ff;--green:#35dd91;--red:#ff5d6c;--amber:#f0c94f}}
    body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740 0,#06111b 34%,#050d15 100%);color:var(--text);font-family:Inter,Arial,sans-serif;min-height:100vh}}
    .shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}
    .topbar{{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:14px}}
    .brand{{display:flex;align-items:center;gap:12px}}.logo{{font-size:30px;color:#2b9cff}}h1{{font-size:24px;margin:0}}.live{{font-size:12px;color:var(--green);font-weight:900;margin-left:6px}}.subtitle{{font-size:12px;color:#9bb0c1;margin-top:3px}}
    .search{{min-width:360px;max-width:520px;width:34%;background:#07131e;border:1px solid #1b3448;color:white;border-radius:10px;padding:12px 14px;outline:none}}
    .cards{{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:10px;margin-bottom:14px}}.card{{background:linear-gradient(180deg,#0b1b29,#091621);border:1px solid #19344a;border-radius:12px;padding:14px 16px;box-shadow:inset 0 1px rgba(255,255,255,.02)}}.card .label{{font-size:11px;color:#8ca5b8;letter-spacing:.04em}}.card .value{{font-size:27px;font-weight:900;margin-top:6px}}.card .hint{{font-size:11px;color:#7892a6;margin-top:3px}}
    .filters{{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}.filterset{{display:flex;gap:7px;flex-wrap:wrap}}button.filter{{background:#081520;color:#dce8f2;border:1px solid #25445b;border-radius:9px;padding:9px 13px;font-weight:800;cursor:pointer}}button.filter.active{{background:linear-gradient(180deg,#337fff,#2169eb);border-color:#4c91ff;color:white}}
    .panel{{background:rgba(6,17,27,.82);border:1px solid #163247;border-radius:13px;padding:14px;box-shadow:0 20px 70px rgba(0,0,0,.2)}}.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}}.panel-title{{font-size:21px;font-weight:900}}.scan{{font-size:12px;color:#91a8b9}}.scan b{{color:var(--green)}}
    .tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1450px;background:#07131e}}thead{{position:sticky;top:0;background:#0b1b28;z-index:2}}th{{text-align:left;color:#829db2;font-size:10px;letter-spacing:.055em;padding:11px 10px;border-bottom:1px solid #1b3a51}}td{{padding:11px 10px;border-bottom:1px solid #10283a;font-size:12px;vertical-align:middle;white-space:nowrap}}tbody tr{{cursor:pointer;transition:.15s}}tbody tr:hover{{background:#0c1d2a}}.rank{{color:#5e7b91;width:36px}}.asset{{font-size:14px;font-weight:900}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}
    .side{{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:6px 9px;font-weight:900;font-size:11px}}.side.long{{background:#0c3527;color:#4de3a0}}.side.short{{background:#3a1720;color:#ff7c87}}.side.wait{{background:#3a3515;color:#ead76e}}
    .setup{{font-weight:800}}.confidence{{font-size:14px;font-weight:900}}.confidence.ready{{color:#7ff0b7}}.confidence.learning{{color:#e8cf68}}.move{{font-size:14px;font-weight:900}}.move.up{{color:var(--green)}}.move.down{{color:var(--red)}}.duration-text{{font-weight:800;color:#c8d8e5}}.num{{font-variant-numeric:tabular-nums}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.rr{{font-weight:900}}
    .status{{display:inline-block;border-radius:7px;padding:6px 9px;font-size:10px;font-weight:900}}.status.active{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.chart{{background:#2b74f7;color:white;text-decoration:none;border-radius:7px;padding:7px 9px;font-weight:900;font-size:10px}}.empty{{padding:28px;color:#9db0bf}}
    .foot{{display:flex;justify-content:space-between;color:#668296;font-size:10px;margin-top:10px;gap:16px;flex-wrap:wrap}}
    @media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.search{{min-width:260px;width:45%}}}}@media(max-width:700px){{.shell{{padding:12px}}.topbar{{align-items:flex-start;flex-direction:column}}.search{{width:100%;min-width:0}}.cards{{grid-template-columns:repeat(2,1fr)}}.card .value{{font-size:22px}}}}
    </style></head><body><div class="shell">
      <div class="topbar"><div class="brand"><div class="logo">▥</div><div><h1>Crypto Signals <span class="live">● LIVE</span></h1><div class="subtitle">Multi-timeframe AI research · unified opportunities · 24/7</div></div></div><input id="search" class="search" placeholder="Search any coin (e.g. BTC, XRP, PONS...)" autocomplete="off"></div>
      <div class="cards">
        <div class="card"><div class="label">TOTAL OPPORTUNITIES</div><div class="value">{len(rows)}</div><div class="hint">current unified signals</div></div>
        <div class="card"><div class="label">HIGH CONFIDENCE</div><div class="value">{high_confidence}</div><div class="hint">verified ≥65% forward accuracy</div></div>
        <div class="card"><div class="label">STRONG MOVES</div><div class="value">{strong_moves}</div><div class="hint">100%+ expected move</div></div>
        <div class="card"><div class="label">TRADE SETUPS</div><div class="value">{trade_setups}</div><div class="hint">currently actionable</div></div>
        <div class="card"><div class="label">AVG EVIDENCE</div><div class="value">{avg_evidence:.0f}</div><div class="hint">signal strength / 100</div></div>
        <div class="card"><div class="label">REFRESH</div><div class="value">60s</div><div class="hint">automatic update</div></div>
      </div>
      <div class="filters"><div class="filterset"><button class="filter active" data-filter="all">✧ All Signals</button><button class="filter" data-filter="high">★ High Confidence</button><button class="filter" data-filter="strong">🚀 Strong Moves (2×+)</button><button class="filter" data-filter="active">◉ Trade Setups</button><button class="filter" data-filter="long">↗ Top Bullish</button><button class="filter" data-filter="short">↘ Top Bearish</button></div></div>
      <div class="panel"><div class="panel-head"><div class="panel-title">Live Crypto Signals</div><div class="scan"><b>●</b> Scanning all internal timeframes · one strongest opportunity per asset · refreshes every 60s</div></div>{table}{empty}<div class="foot"><span>Fixed 6h / 12h / 24h / 48h / 72h / 7d buckets are intentionally hidden. The system chooses the expected move duration and displays it directly.</span><span>Confidence is shown only when supported by genuine forward calibration; otherwise it remains LEARNING.</span></div></div>
    </div><script>
    const rows=[...document.querySelectorAll('.signal-row')];const buttons=[...document.querySelectorAll('.filter')];const search=document.getElementById('search');let active='all';
    function apply(){{const q=(search.value||'').trim().toLowerCase();rows.forEach(r=>{{const matchesSearch=!q||r.dataset.search.includes(q);let matches=true;if(active==='high')matches=parseFloat(r.dataset.confidence)>=.65;if(active==='strong')matches=parseFloat(r.dataset.move)>=100;if(active==='active')matches=r.dataset.status==='active';if(active==='long')matches=r.dataset.side==='long';if(active==='short')matches=r.dataset.side==='short';r.style.display=(matches&&matchesSearch)?'':'none';}})}}
    buttons.forEach(b=>b.addEventListener('click',()=>{{active=b.dataset.filter;buttons.forEach(x=>x.classList.toggle('active',x===b));apply();}}));search.addEventListener('input',apply);
    </script></body></html>""")


def signal_chart_data(request: Request,signal_id:int):
    if not _authorized(request):
        return JSONResponse({"ok":False,"error":"unauthorized"},status_code=401)
    row=fetch_signal_by_id(signal_id)
    if not row:
        return JSONResponse({"ok":False,"error":"signal_not_found"},status_code=404)
    symbol=str(row.get("symbol") or "BTC-USDT")
    duration=_duration(row)
    bar="4H" if duration in {"48h","72h","7d"} else "1H"
    candles=get_candles(symbol,bar=bar,limit=240)
    return JSONResponse({"ok":True,"symbol":symbol,"bar":bar,"candles":[{"time":int(c["ts"]//1000),"open":c["open"],"high":c["high"],"low":c["low"],"close":c["close"]} for c in candles]})


def signal_detail_page(request: Request,signal_id:int):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login",status_code=303)
    row=fetch_signal_by_id(signal_id)
    if not row:
        return HTMLResponse("Signal not found",status_code=404)
    lo,hi=_entry_zone(row)
    label=_trade_label(row)
    direction=html.escape(str(row.get("direction") or ""))
    symbol=html.escape(str(row.get("symbol") or ""))
    duration=html.escape(_estimated_duration(row))
    score=float(row.get("evidence_score") or 0)
    calibration=_calibration_metrics(row)
    rr=float(row.get("risk_reward") or 0)
    entry=float(row.get("entry_price") or 0)
    stop=float(row.get("stop_loss") or 0)
    t1=float(row.get("target_1") or 0)
    t2=float(row.get("target_2") or 0)
    stop_pct=_signed_pct(row,"stop_loss")
    t1_pct=_signed_pct(row,"target_1")
    t2_pct=_signed_pct(row,"target_2")
    buy=direction.upper()=="LONG"
    marker_color="#00c853" if buy else "#ff3d3d" if direction.upper()=="SHORT" else "#f5c542"
    marker_shape="arrowUp" if buy else "arrowDown" if direction.upper()=="SHORT" else "circle"
    marker_position="belowBar" if buy else "aboveBar"
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{symbol} signal chart</title><script src="https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;background:#06111b;color:#edf2f7;font-family:Arial,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:14px}}.top{{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}}h1{{font-size:22px;margin:0}}.badge{{font-size:20px;font-weight:900;color:{marker_color}}}.back{{color:white;text-decoration:none;background:#26394c;padding:9px 12px;border-radius:8px}}.chartbox{{position:relative;background:#0b1118;border:1px solid #26394c;border-radius:12px;overflow:hidden}}#chart{{width:100%;height:70vh;min-height:520px}}.hud{{position:absolute;left:14px;top:12px;z-index:5;background:rgba(8,16,24,.88);border:1px solid #26394c;border-radius:9px;padding:9px 11px;font-size:12px;pointer-events:none}}.hud b{{font-size:14px}}.legend{{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}}.chip{{background:#111c27;border:1px solid #26394c;padding:8px 10px;border-radius:8px;font-size:12px}}.stop{{color:#ff9a9a}}.target{{color:#91e8b7}}.entry{{color:#8cb5ff}}.accuracy{{color:#9ee6c2}}.note{{color:#8397aa;font-size:11px;margin-top:10px}}</style></head><body><div class="wrap"><div class="top"><div><h1>{symbol} · estimated {duration}</h1><div class="badge">{label} {direction}</div></div><a class="back" href="/dashboard">← Back to signals</a></div><div class="chartbox"><div class="hud"><b>{label} · estimated {duration}</b><br>Forward accuracy {calibration['accuracy']} · 95% floor {calibration['floor']} · {calibration['n']}<br>Expected T1 {_pct_text(t1_pct)} · T2 {_pct_text(t2_pct)}<br>Stop {_pct_text(stop_pct)} · R:R {rr:.2f} · Evidence {score:.0f}</div><div id="chart"></div></div><div class="legend"><span class="chip accuracy">ACCURACY {calibration['accuracy']} · FLOOR {calibration['floor']} · {calibration['n']}</span><span class="chip entry">ENTRY {_price(entry)} · zone {_price(lo)}–{_price(hi)}</span><span class="chip stop">STOP {_price(stop)} ({_pct_text(stop_pct)})</span><span class="chip target">T1 {_price(t1)} ({_pct_text(t1_pct)})</span><span class="chip target">T2 {_price(t2)} ({_pct_text(t2_pct)})</span></div><div class="note">Expected duration is displayed as a human-readable estimate. Confidence is measured only from independent resolved forward forecasts; evidence is current signal strength.</div></div><script>(async function(){{const el=document.getElementById('chart');const chart=LightweightCharts.createChart(el,{{layout:{{background:{{color:'#0b1118'}},textColor:'#c7d3df'}},grid:{{vertLines:{{color:'#17222d'}},horzLines:{{color:'#17222d'}}}},rightPriceScale:{{borderColor:'#304052'}},timeScale:{{borderColor:'#304052',timeVisible:true,secondsVisible:false}},crosshair:{{mode:LightweightCharts.CrosshairMode.Normal}}}});const series=chart.addCandlestickSeries({{upColor:'#26a69a',downColor:'#ef5350',borderVisible:false,wickUpColor:'#26a69a',wickDownColor:'#ef5350'}});const res=await fetch('/dashboard/signal/{signal_id}/chart-data',{{credentials:'same-origin'}});const data=await res.json();if(!data.ok||!data.candles||!data.candles.length){{el.innerHTML='<div style="padding:30px;color:#ffb2b2">Chart data unavailable.</div>';return;}}series.setData(data.candles);const lastTime=data.candles[data.candles.length-1].time;series.setMarkers([{{time:lastTime,position:'{marker_position}',color:'{marker_color}',shape:'{marker_shape}',text:'{label}'}}]);const lines=[[{entry},'#2962ff','ENTRY {_price(entry)}'],[{lo},'#5a83ff','ENTRY LOW {_price(lo)}'],[{hi},'#5a83ff','ENTRY HIGH {_price(hi)}'],[{stop},'#ff3d3d','STOP {_pct_text(stop_pct)}'],[{t1},'#00c853','T1 {_pct_text(t1_pct)}'],[{t2},'#00e676','T2 {_pct_text(t2_pct)}']];lines.forEach(([price,color,title])=>{{if(price>0)series.createPriceLine({{price,color,lineWidth:2,lineStyle:0,axisLabelVisible:true,title}});}});chart.timeScale().fitContent();const resize=()=>chart.applyOptions({{width:el.clientWidth,height:el.clientHeight}});window.addEventListener('resize',resize);resize();}})().catch(()=>{{document.getElementById('chart').innerHTML='<div style="padding:30px;color:#ffb2b2">Chart failed to load.</div>';}});</script></body></html>""")

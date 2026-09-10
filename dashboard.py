import base64
import hashlib
import hmac
import html
import time

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from config import DASHBOARD_SECRET
from db import fetch_ranked_opportunities, fetch_signal_by_id
from market_data import get_candles

SESSION_COOKIE = "crypto_dashboard_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


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
    return "BUY" if direction == "LONG" else "SELL"


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
    return "7d" if str(row.get("timeframe") or row.get("horizon") or "24h") == "7d" else "24h"


def _calibration_metrics(row):
    """Expose only genuine empirical forward calibration; never synthesize accuracy."""
    calibration = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(calibration, dict):
        return {
            "accuracy": "LEARNING",
            "floor": "—",
            "n": "N=0/30",
            "samples": 0,
            "minimum_samples": 30,
            "ready": False,
        }
    try:
        samples = max(0, int(calibration.get("independent_samples") or calibration.get("samples") or 0))
    except (TypeError, ValueError):
        samples = 0
    try:
        minimum = max(1, int(calibration.get("minimum_samples") or 30))
    except (TypeError, ValueError):
        minimum = 30
    ready = bool(calibration.get("ready"))
    precision = calibration.get("empirical_precision") if ready else None
    floor = calibration.get("precision_95pct_lower") if ready else None
    try:
        accuracy_text = f"{float(precision) * 100.0:.0f}%" if precision is not None else "LEARNING"
    except (TypeError, ValueError):
        accuracy_text = "LEARNING"
    try:
        floor_text = f"{float(floor) * 100.0:.0f}%" if floor is not None else "—"
    except (TypeError, ValueError):
        floor_text = "—"
    n_text = f"N={samples}" if ready else f"N={samples}/{minimum}"
    return {
        "accuracy": accuracy_text,
        "floor": floor_text,
        "n": n_text,
        "samples": samples,
        "minimum_samples": minimum,
        "ready": ready,
    }


def login_page(error=""):
    if not DASHBOARD_SECRET:
        error = "Dashboard authentication is not configured yet. Set DASHBOARD_SECRET privately in Render before using this page."
    err = f'<div class="error">{html.escape(error)}</div>' if error else ""
    disabled = " disabled" if not DASHBOARD_SECRET else ""
    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crypto Signal Dashboard</title><style>
body{{font-family:Arial,sans-serif;background:#0b0f14;color:#edf2f7;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.box{{width:min(440px,90vw);background:#121821;border:1px solid #263240;border-radius:16px;padding:28px}}
input,button{{box-sizing:border-box;width:100%;padding:13px;border-radius:10px;border:1px solid #344254;font-size:16px}}
input{{background:#0b0f14;color:white;margin:12px 0}}button{{background:#edf2f7;color:#0b0f14;font-weight:bold;cursor:pointer}}button:disabled{{opacity:.45;cursor:not-allowed}}
small{{color:#93a4b8}}.error{{background:#4a1c1c;padding:10px;border-radius:8px;margin:10px 0}}
</style></head><body><div class="box"><h2>Crypto Signal Dashboard</h2>
<p>Private dashboard for ranked 24h and 7d signal candidates.</p>{err}
<form method="post" action="/dashboard/login"><input name="secret" type="password" autocomplete="current-password" placeholder="Private dashboard password" required{disabled}><button{disabled}>Unlock dashboard</button></form>
<p><small>The password is submitted only to your Render service over HTTPS and replaced by a signed HttpOnly session cookie. Do not paste it into chat.</small></p>
</div></body></html>""")


async def handle_login(request: Request):
    if not DASHBOARD_SECRET:
        return login_page()
    raw = (await request.body()).decode("utf-8", errors="replace")
    form = __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs(raw, keep_blank_values=True)
    supplied = (form.get("secret") or [""])[0]
    if not hmac.compare_digest(supplied, DASHBOARD_SECRET):
        return login_page("Incorrect password.")
    expires = int(time.time()) + SESSION_TTL_SECONDS
    response = RedirectResponse("/dashboard?horizon=24h", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _session_token(expires),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/dashboard",
    )
    return response


def dashboard_page(request: Request, horizon="24h"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    horizon = "7d" if horizon == "7d" else "24h"
    rows = fetch_ranked_opportunities(horizon=horizon, limit=20)
    table_rows = []
    for rank, row in enumerate(rows, 1):
        lo, hi = _entry_zone(row)
        label = _trade_label(row)
        cls = label.lower()
        score = float(row.get("evidence_score") or 0)
        rr = float(row.get("risk_reward") or 0)
        calibration = _calibration_metrics(row)
        stop_pct = _signed_pct(row, "stop_loss")
        t1_pct = _signed_pct(row, "target_1")
        t2_pct = _signed_pct(row, "target_2")
        symbol = html.escape(str(row.get("symbol") or ""))
        signal_id = int(row.get("id") or 0)
        detail = f"/dashboard/signal/{signal_id}"
        accuracy_cls = "accuracy-ready" if calibration["ready"] else "accuracy-learning"
        table_rows.append(f"""
<tr onclick="location.href='{detail}'">
<td class="rank">{rank}</td>
<td class="symbol">{symbol}</td>
<td><span class="pill {cls}">{label}</span></td>
<td>{html.escape(_duration(row))}</td>
<td class="num {accuracy_cls}">{calibration['accuracy']}<small>forward</small></td>
<td class="num">{calibration['floor']}<small>95% floor</small></td>
<td class="num">{calibration['n']}<small>independent</small></td>
<td class="num">{_price(lo)}–{_price(hi)}</td>
<td class="num stop">{_price(row.get('stop_loss'))}<small>{_pct_text(stop_pct)}</small></td>
<td class="num target">{_price(row.get('target_1'))}<small>{_pct_text(t1_pct)}</small></td>
<td class="num target">{_price(row.get('target_2'))}<small>{_pct_text(t2_pct)}</small></td>
<td class="num">{rr:.2f}</td>
<td class="num">{score:.0f}<small>strength</small></td>
<td><a class="tv" href="{detail}">VIEW CHART</a></td>
</tr>""")
    empty = '<div class="empty">No recent candidates for this horizon yet. The engine will not invent trades to fill the list.</div>' if not table_rows else ""
    table = "" if not table_rows else f"""
<div class="tablewrap"><table><thead><tr>
<th>#</th><th>CRYPTO</th><th>SIGNAL</th><th>DURATION</th><th>ACCURACY</th><th>95% FLOOR</th><th>SAMPLE</th><th>ENTRY AREA</th><th>STOP LOSS</th><th>EXPECTED T1</th><th>EXPECTED T2</th><th>R:R</th><th>EVIDENCE</th><th>CHART</th>
</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>"""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Crypto Signals</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#eaf1f8;font-family:Arial,sans-serif}}.wrap{{max-width:1800px;margin:auto;padding:18px}}header{{display:flex;justify-content:space-between;gap:16px;align-items:end;flex-wrap:wrap}}h1{{margin:0 0 4px;font-size:24px}}.sub{{color:#91a4b7;font-size:13px}}nav a{{color:#eaf1f8;text-decoration:none;border:1px solid #32465a;border-radius:8px;padding:8px 11px;margin-left:6px;display:inline-block}}nav a.active{{background:#eaf1f8;color:#081018}}.note{{background:#0d1823;border-left:3px solid #405a72;padding:9px 12px;margin:12px 0;color:#aebdca;font-size:12px}}.tablewrap{{overflow-x:auto;border:1px solid #213244;border-radius:10px;background:#0c1620}}table{{width:100%;border-collapse:collapse;min-width:1480px}}thead{{background:#111c27;position:sticky;top:0}}th{{font-size:10px;letter-spacing:.04em;color:#7f94a8;text-align:left;padding:9px 8px;border-bottom:1px solid #26394c;white-space:nowrap}}td{{padding:8px;border-bottom:1px solid #172635;font-size:12px;white-space:nowrap;vertical-align:middle}}tbody tr{{cursor:pointer}}tbody tr:hover{{background:#101d29}}.rank{{color:#60778d;width:34px}}.symbol{{color:#f0f6fb;font-weight:800;font-size:13px}}.num{{font-variant-numeric:tabular-nums}}td small{{display:block;color:#8296a9;font-size:10px;margin-top:2px}}.pill{{font-weight:800;padding:4px 7px;border-radius:999px;font-size:10px}}.buy{{background:#123c2c;color:#9ee6c2}}.sell{{background:#482020;color:#ffb2b2}}.wait{{background:#403815;color:#eadb93}}.stop small{{color:#e0a0a0}}.target small{{color:#99d6b5}}.accuracy-ready{{font-weight:900;color:#9ee6c2}}.accuracy-learning{{font-weight:800;color:#eadb93}}.tv{{background:#2962ff;color:white;text-decoration:none;font-weight:800;border-radius:7px;padding:7px 9px;display:inline-block}}.empty{{padding:24px;background:#111c27;border-radius:10px;margin-top:14px}}@media(max-width:720px){{.wrap{{padding:10px}}h1{{font-size:20px}}th,td{{padding:7px 6px}}}}
</style></head><body><div class="wrap"><header><div><h1>Crypto signals</h1><div class="sub">Latest researched 24h/7d signal stream. Refreshes every 60 seconds.</div></div><nav><a class="{'active' if horizon=='24h' else ''}" href="/dashboard?horizon=24h">24h</a><a class="{'active' if horizon=='7d' else ''}" href="/dashboard?horizon=7d">7d</a></nav></header>
<div class="note"><b>Accuracy</b> is empirical forward hit rate from genuinely resolved, non-overlapping comparable forecasts. <b>95% Floor</b> is the conservative Wilson lower bound. <b>N</b> is the number of independent forecasts. Until the required sample is reached, Accuracy shows LEARNING. <b>Evidence</b> remains current signal strength, not a probability of being correct.</div>{table}{empty}</div></body></html>""")


def signal_chart_data(request: Request, signal_id: int):
    if not _authorized(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    row = fetch_signal_by_id(signal_id)
    if not row:
        return JSONResponse({"ok": False, "error": "signal_not_found"}, status_code=404)
    symbol = str(row.get("symbol") or "BTC-USDT")
    bar = "4H" if _duration(row) == "7d" else "1H"
    candles = get_candles(symbol, bar=bar, limit=240)
    return JSONResponse({
        "ok": True,
        "symbol": symbol,
        "bar": bar,
        "candles": [
            {
                "time": int(c["ts"] // 1000),
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
            }
            for c in candles
        ],
    })


def signal_detail_page(request: Request, signal_id: int):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    row = fetch_signal_by_id(signal_id)
    if not row:
        return HTMLResponse("Signal not found", status_code=404)
    lo, hi = _entry_zone(row)
    label = _trade_label(row)
    direction = html.escape(str(row.get("direction") or ""))
    symbol = html.escape(str(row.get("symbol") or ""))
    duration = html.escape(_duration(row))
    score = float(row.get("evidence_score") or 0)
    calibration = _calibration_metrics(row)
    rr = float(row.get("risk_reward") or 0)
    entry = float(row.get("entry_price") or 0)
    stop = float(row.get("stop_loss") or 0)
    t1 = float(row.get("target_1") or 0)
    t2 = float(row.get("target_2") or 0)
    stop_pct = _signed_pct(row, "stop_loss")
    t1_pct = _signed_pct(row, "target_1")
    t2_pct = _signed_pct(row, "target_2")
    buy = label == "BUY"
    marker_color = "#00c853" if buy else "#ff3d3d" if label == "SELL" else "#f5c542"
    marker_shape = "arrowUp" if buy else "arrowDown" if label == "SELL" else "circle"
    marker_position = "belowBar" if buy else "aboveBar"
    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{symbol} signal chart</title>
<script src="https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"></script>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#edf2f7;font-family:Arial,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:14px}}.top{{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}}h1{{font-size:22px;margin:0}}.badge{{font-size:20px;font-weight:900;color:{marker_color}}}.back{{color:white;text-decoration:none;background:#26394c;padding:9px 12px;border-radius:8px}}.chartbox{{position:relative;background:#0b1118;border:1px solid #26394c;border-radius:12px;overflow:hidden}}#chart{{width:100%;height:70vh;min-height:520px}}.hud{{position:absolute;left:14px;top:12px;z-index:5;background:rgba(8,16,24,.88);border:1px solid #26394c;border-radius:9px;padding:9px 11px;font-size:12px;pointer-events:none}}.hud b{{font-size:14px}}.legend{{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}}.chip{{background:#111c27;border:1px solid #26394c;padding:8px 10px;border-radius:8px;font-size:12px}}.stop{{color:#ff9a9a}}.target{{color:#91e8b7}}.entry{{color:#8cb5ff}}.accuracy{{color:#9ee6c2}}.note{{color:#8397aa;font-size:11px;margin-top:10px}}@media(max-width:700px){{#chart{{height:62vh;min-height:430px}}.hud{{font-size:10px}}}}
</style></head><body><div class="wrap">
<div class="top"><div><h1>{symbol} · {duration}</h1><div class="badge">{label} {direction}</div></div><a class="back" href="/dashboard?horizon={duration}">← Back to signals</a></div>
<div class="chartbox"><div class="hud"><b>{label} · {duration}</b><br>Forward accuracy {calibration['accuracy']} · 95% floor {calibration['floor']} · {calibration['n']}<br>Expected T1 {_pct_text(t1_pct)} · T2 {_pct_text(t2_pct)}<br>Stop {_pct_text(stop_pct)} · R:R {rr:.2f} · Evidence {score:.0f}</div><div id="chart"></div></div>
<div class="legend"><span class="chip accuracy">ACCURACY {calibration['accuracy']} · FLOOR {calibration['floor']} · {calibration['n']}</span><span class="chip entry">ENTRY {_price(entry)} · zone {_price(lo)}–{_price(hi)}</span><span class="chip stop">STOP {_price(stop)} ({_pct_text(stop_pct)})</span><span class="chip target">T1 {_price(t1)} ({_pct_text(t1_pct)})</span><span class="chip target">T2 {_price(t2)} ({_pct_text(t2_pct)})</span></div>
<div class="note">Accuracy is measured forward calibration from independent resolved forecasts; Evidence is current signal strength. The chart uses TradingView Lightweight Charts with live market candles. Signal levels come from the system's stored researched signal record; visualization does not create trade authority.</div>
</div>
<script>
(async function() {{
  const el = document.getElementById('chart');
  const chart = LightweightCharts.createChart(el, {{
    layout: {{ background: {{ color: '#0b1118' }}, textColor: '#c7d3df' }},
    grid: {{ vertLines: {{ color: '#17222d' }}, horzLines: {{ color: '#17222d' }} }},
    rightPriceScale: {{ borderColor: '#304052' }},
    timeScale: {{ borderColor: '#304052', timeVisible: true, secondsVisible: false }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
  }});
  const series = chart.addCandlestickSeries({{
    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
    wickUpColor: '#26a69a', wickDownColor: '#ef5350'
  }});
  const res = await fetch('/dashboard/signal/{signal_id}/chart-data', {{credentials:'same-origin'}});
  const data = await res.json();
  if (!data.ok || !data.candles || !data.candles.length) {{
    el.innerHTML = '<div style="padding:30px;color:#ffb2b2">Chart data unavailable.</div>';
    return;
  }}
  series.setData(data.candles);
  const lastTime = data.candles[data.candles.length - 1].time;
  series.setMarkers([{{ time:lastTime, position:'{marker_position}', color:'{marker_color}', shape:'{marker_shape}', text:'{label}' }}]);
  const lines = [
    [{entry}, '#2962ff', 'ENTRY {_price(entry)}'],
    [{lo}, '#5a83ff', 'ENTRY LOW {_price(lo)}'],
    [{hi}, '#5a83ff', 'ENTRY HIGH {_price(hi)}'],
    [{stop}, '#ff3d3d', 'STOP {_pct_text(stop_pct)}'],
    [{t1}, '#00c853', 'T1 {_pct_text(t1_pct)}'],
    [{t2}, '#00e676', 'T2 {_pct_text(t2_pct)}']
  ];
  lines.forEach(([price,color,title]) => {{
    if (price > 0) series.createPriceLine({{price, color, lineWidth:2, lineStyle:0, axisLabelVisible:true, title}});
  }});
  chart.timeScale().fitContent();
  const resize = () => chart.applyOptions({{width: el.clientWidth, height: el.clientHeight}});
  window.addEventListener('resize', resize); resize();
}})().catch(() => {{ document.getElementById('chart').innerHTML='<div style="padding:30px;color:#ffb2b2">Chart failed to load.</div>'; }});
</script></body></html>""")
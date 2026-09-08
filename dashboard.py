import base64
import hashlib
import hmac
import html
import time
import urllib.parse

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import DASHBOARD_SECRET
from db import fetch_ranked_opportunities, fetch_signal_by_id

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


def _pct_from_entry(row, field):
    try:
        entry = float(row.get("entry_price") or 0)
        value = float(row.get(field) or 0)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or value <= 0:
        return None
    return abs(value - entry) / entry * 100.0


def _pct_text(value):
    return "—" if value is None else f"{value:.2f}%"


def _duration(row):
    horizon = str(row.get("timeframe") or "24h")
    return "24h" if horizon == "24h" else "7d"


def _tv_url(row):
    symbol = str(row.get("symbol") or "BTC-USDT").replace("-", "")
    interval = "60" if str(row.get("timeframe")) == "24h" else "240"
    params = urllib.parse.urlencode({"symbol": f"OKX:{symbol}", "interval": interval})
    return f"https://www.tradingview.com/chart/?{params}"


def _risk_visual(row):
    try:
        values = {
            "stop": float(row.get("stop_loss")),
            "entry": float(row.get("entry_price")),
            "t1": float(row.get("target_1")),
            "t2": float(row.get("target_2")),
        }
    except (TypeError, ValueError):
        return ""
    lo, hi = min(values.values()), max(values.values())
    if hi <= lo:
        return ""
    labels = {"stop": "STOP", "entry": "ENTRY", "t1": "T1", "t2": "T2"}
    markers = []
    for key, value in values.items():
        pct = (value - lo) / (hi - lo) * 100
        markers.append(
            f'<span class="marker {key}" style="left:{pct:.2f}%"><b>{labels[key]}</b><small>{html.escape(_price(value))}</small></span>'
        )
    return '<div class="riskbar"><div class="riskline"></div>' + "".join(markers) + '</div>'


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
<p><small>The dashboard uses a separate password from the scanner/API secret. The password is submitted only to your Render service over HTTPS and replaced by a signed HttpOnly session cookie. Do not paste it into chat.</small></p>
</div></body></html>""")


async def handle_login(request: Request):
    if not DASHBOARD_SECRET:
        return login_page()
    raw = (await request.body()).decode("utf-8", errors="replace")
    form = urllib.parse.parse_qs(raw, keep_blank_values=True)
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


def _authorized(request: Request):
    return _valid_session(request.cookies.get(SESSION_COOKIE, ""))


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
        stop_pct = _pct_from_entry(row, "stop_loss")
        t1_pct = _pct_from_entry(row, "target_1")
        t2_pct = _pct_from_entry(row, "target_2")
        symbol = html.escape(str(row.get("symbol") or ""))
        detail = f"/dashboard/signal/{int(row.get('id') or 0)}"
        table_rows.append(f"""
<tr>
<td class="rank">{rank}</td>
<td class="symbol"><a href="{detail}">{symbol}</a></td>
<td><span class="pill {cls}">{label}</span></td>
<td>{html.escape(_duration(row))}</td>
<td class="num">{_price(lo)}–{_price(hi)}</td>
<td class="num stop">{_price(row.get('stop_loss'))}<small>{_pct_text(stop_pct)}</small></td>
<td class="num target">{_price(row.get('target_1'))}<small>{_pct_text(t1_pct)}</small></td>
<td class="num target">{_price(row.get('target_2'))}<small>{_pct_text(t2_pct)}</small></td>
<td class="num">{rr:.2f}</td>
<td class="num">{score:.0f}</td>
<td><a class="tv" target="_blank" rel="noopener" href="{html.escape(_tv_url(row))}">TradingView ↗</a></td>
</tr>""")
    empty = '<div class="empty">No recent candidates for this horizon yet. The system will not invent trades to fill the list.</div>' if not table_rows else ""
    table = "" if not table_rows else f"""
<div class="tablewrap"><table><thead><tr>
<th>#</th><th>CRYPTO</th><th>SIGNAL</th><th>DURATION</th><th>ENTRY AREA</th><th>STOP LOSS</th><th>EXPECTED T1</th><th>EXPECTED T2</th><th>R:R</th><th>EVIDENCE</th><th>CHART</th>
</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>"""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Top Crypto Opportunities</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#eaf1f8;font-family:Arial,sans-serif}}.wrap{{max-width:1600px;margin:auto;padding:18px}}header{{display:flex;justify-content:space-between;gap:16px;align-items:end;flex-wrap:wrap}}h1{{margin:0 0 4px;font-size:24px}}.sub{{color:#91a4b7;font-size:13px}}nav a{{color:#eaf1f8;text-decoration:none;border:1px solid #32465a;border-radius:8px;padding:8px 11px;margin-left:6px;display:inline-block}}nav a.active{{background:#eaf1f8;color:#081018}}.note{{background:#0d1823;border-left:3px solid #405a72;padding:9px 12px;margin:12px 0;color:#aebdca;font-size:12px}}.tablewrap{{overflow-x:auto;border:1px solid #213244;border-radius:10px;background:#0c1620}}table{{width:100%;border-collapse:collapse;min-width:1120px}}thead{{background:#111c27;position:sticky;top:0}}th{{font-size:10px;letter-spacing:.04em;color:#7f94a8;text-align:left;padding:9px 8px;border-bottom:1px solid #26394c;white-space:nowrap}}td{{padding:8px;border-bottom:1px solid #172635;font-size:12px;white-space:nowrap;vertical-align:middle}}tbody tr:hover{{background:#101d29}}.rank{{color:#60778d;width:34px}}.symbol a{{color:#f0f6fb;font-weight:800;text-decoration:none;font-size:13px}}.num{{font-variant-numeric:tabular-nums}}td small{{display:block;color:#8296a9;font-size:10px;margin-top:2px}}.pill{{font-weight:800;padding:4px 7px;border-radius:999px;font-size:10px}}.buy{{background:#123c2c;color:#9ee6c2}}.sell{{background:#482020;color:#ffb2b2}}.wait{{background:#403815;color:#eadb93}}.stop small{{color:#e0a0a0}}.target small{{color:#99d6b5}}.tv{{background:#2962ff;color:white;text-decoration:none;font-weight:800;border-radius:7px;padding:7px 9px;display:inline-block}}.empty{{padding:24px;background:#111c27;border-radius:10px;margin-top:14px}}@media(max-width:720px){{.wrap{{padding:10px}}h1{{font-size:20px}}th,td{{padding:7px 6px}}}}
</style></head><body><div class="wrap"><header><div><h1>Crypto signals</h1><div class="sub">Compact ranked view. Refreshes every 60 seconds.</div></div><nav><a class="{'active' if horizon=='24h' else ''}" href="/dashboard?horizon=24h">24h</a><a class="{'active' if horizon=='7d' else ''}" href="/dashboard?horizon=7d">7d</a></nav></header>
<div class="note">BUY/SELL appears only for validated engine TRADE candidates; otherwise WAIT. Percent values under stop/targets show distance from modeled entry. Click any crypto for full signal detail or TradingView for the live chart.</div>{table}{empty}</div></body></html>""")


def signal_detail_page(request: Request, signal_id: int):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    row = fetch_signal_by_id(signal_id)
    if not row:
        return HTMLResponse("Signal not found", status_code=404)
    lo, hi = _entry_zone(row)
    label = _trade_label(row)
    symbol = html.escape(str(row.get("symbol") or ""))
    stop_pct = _pct_from_entry(row, "stop_loss")
    t1_pct = _pct_from_entry(row, "target_1")
    t2_pct = _pct_from_entry(row, "target_2")
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{symbol} signal</title><style>
body{{background:#081018;color:#edf2f7;font-family:Arial,sans-serif;margin:0}}.wrap{{max-width:900px;margin:auto;padding:25px}}.panel{{background:#111c27;border:1px solid #26394c;border-radius:16px;padding:22px}}h1{{margin-top:0}}.big{{font-size:28px;font-weight:bold}}.levels{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:18px 0}}.levels div{{background:#0a141e;padding:15px;border-radius:10px}}small{{display:block;color:#8197ab;margin-bottom:4px}}.pct{{display:block;color:#a9b8c6;margin-top:5px;font-size:13px}}a{{display:inline-block;color:#081018;background:#edf2f7;text-decoration:none;padding:11px 14px;border-radius:9px;font-weight:bold;margin:8px 8px 0 0}}.tv{{background:#2962ff;color:white;font-size:17px;padding:14px 18px}}.back{{background:#26394c;color:white}}.riskbar{{height:90px;position:relative;margin:30px 25px}}.riskline{{position:absolute;top:38px;left:0;right:0;height:5px;background:#4a647a}}.marker{{position:absolute;top:16px;transform:translateX(-50%);text-align:center;font-size:11px}}.marker:after{{content:'';display:block;width:3px;height:45px;background:#d7e0e8;margin:auto}}.marker small{{white-space:nowrap}}
</style></head><body><div class="wrap"><div class="panel"><h1>{symbol} — {html.escape(_duration(row))}</h1><div class="big">{label} · {html.escape(str(row.get('direction') or ''))}</div>
<div class="levels"><div><small>ENTRY AREA</small><b>{_price(lo)} – {_price(hi)}</b></div><div><small>STOP LOSS</small><b>{_price(row.get('stop_loss'))}</b><span class="pct">{_pct_text(stop_pct)} from entry</span></div><div><small>EXPECTED MOVE T1</small><b>{_price(row.get('target_1'))}</b><span class="pct">{_pct_text(t1_pct)} from entry</span></div><div><small>EXPECTED MOVE T2</small><b>{_price(row.get('target_2'))}</b><span class="pct">{_pct_text(t2_pct)} from entry</span></div></div>{_risk_visual(row)}
<p>Evidence score: <b>{float(row.get('evidence_score') or 0):.0f}</b> · Risk/reward: <b>{float(row.get('risk_reward') or 0):.2f}</b> · Regime: <b>{html.escape(str(row.get('market_regime') or 'UNKNOWN'))}</b></p>
<p>{html.escape(str(row.get('reasoning') or ''))}</p><a class="tv" target="_blank" rel="noopener" href="{html.escape(_tv_url(row))}">OPEN THIS COIN IN TRADINGVIEW ↗</a><a class="back" href="/dashboard?horizon={html.escape(str(row.get('timeframe') or '24h'))}">Back to signal rows</a><p><small>TradingView opens the correct market and interval. Signal, stop and target levels remain displayed in this dashboard because standard TradingView chart URLs cannot inject arbitrary external drawing objects.</small></p></div></div></body></html>""")

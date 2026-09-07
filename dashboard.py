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
    markers=[]
    for key, value in values.items():
        pct=(value-lo)/(hi-lo)*100
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
    cards=[]
    for rank,row in enumerate(rows,1):
        lo,hi=_entry_zone(row)
        label=_trade_label(row)
        cls=label.lower()
        score=float(row.get("evidence_score") or 0)
        rr=float(row.get("risk_reward") or 0)
        symbol=html.escape(str(row.get("symbol") or ""))
        reasoning=html.escape(str(row.get("reasoning") or ""))
        detail=f"/dashboard/signal/{int(row.get('id') or 0)}"
        cards.append(f"""
<article class="card">
<div class="rank">#{rank}</div><div class="main"><div class="top"><h3>{symbol}</h3><span class="pill {cls}">{label}</span></div>
<div class="meta"><span>{html.escape(str(row.get('direction') or ''))}</span><span>Evidence {score:.0f}</span><span>R:R {rr:.2f}</span><span>{html.escape(str(row.get('market_regime') or 'UNKNOWN'))}</span></div>
<div class="grid"><div><small>ENTRY AREA</small><b>{_price(lo)} – {_price(hi)}</b></div><div><small>STOP</small><b>{_price(row.get('stop_loss'))}</b></div><div><small>TARGET 1</small><b>{_price(row.get('target_1'))}</b></div><div><small>TARGET 2</small><b>{_price(row.get('target_2'))}</b></div></div>
{_risk_visual(row)}
<p class="reason">{reasoning[:360]}</p><div class="actions"><a href="{detail}">Signal visual</a><a target="_blank" rel="noopener" href="{html.escape(_tv_url(row))}">Open TradingView</a></div>
</div></article>""")
    empty = '<div class="empty">No recent candidates for this horizon yet. The system will not invent trades to fill the list.</div>' if not cards else ""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Top Crypto Opportunities</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#eaf1f8;font-family:Arial,sans-serif}}.wrap{{max-width:1200px;margin:auto;padding:24px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:end;flex-wrap:wrap}}h1{{margin:0 0 6px}}.sub{{color:#91a4b7}}nav a,.actions a{{color:#eaf1f8;text-decoration:none;border:1px solid #32465a;border-radius:9px;padding:8px 12px;margin-right:7px;display:inline-block}}nav a.active{{background:#eaf1f8;color:#081018}}.card{{display:flex;gap:16px;background:#111c27;border:1px solid #213244;border-radius:14px;padding:16px;margin:14px 0}}.rank{{font-size:24px;color:#6f8498;width:44px}}.main{{flex:1;min-width:0}}.top{{display:flex;justify-content:space-between;align-items:center}}h3{{margin:0;font-size:22px}}.pill{{font-weight:bold;padding:6px 10px;border-radius:999px}}.buy{{background:#123c2c}}.sell{{background:#482020}}.wait{{background:#403815}}.meta{{display:flex;gap:14px;flex-wrap:wrap;color:#a9b8c6;margin:8px 0 13px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.grid div{{background:#0a141e;border-radius:9px;padding:10px}}small{{display:block;color:#7990a6;font-size:11px;margin-bottom:5px}}b{{font-size:15px}}.reason{{color:#b8c5d0;line-height:1.4}}.riskbar{{height:60px;position:relative;margin:16px 20px 5px}}.riskline{{position:absolute;top:25px;left:0;right:0;height:4px;background:#41586c;border-radius:4px}}.marker{{position:absolute;top:10px;transform:translateX(-50%);text-align:center;font-size:10px}}.marker:after{{content:'';display:block;width:2px;height:28px;background:#d7e0e8;margin:auto}}.marker small{{white-space:nowrap;font-size:9px}}.actions{{margin-top:10px}}.empty{{padding:30px;background:#111c27;border-radius:14px;margin-top:20px}}.note{{background:#0d1823;border-left:4px solid #405a72;padding:12px 14px;margin:18px 0;color:#aebdca}}@media(max-width:720px){{.grid{{grid-template-columns:1fr 1fr}}.card{{padding:12px;gap:6px}}.rank{{font-size:18px;width:32px}}}}
</style></head><body><div class="wrap"><header><div><h1>Top crypto opportunities</h1><div class="sub">Ranked from the latest system evidence. Refreshes every 60 seconds.</div></div><nav><a class="{'active' if horizon=='24h' else ''}" href="/dashboard?horizon=24h">Next 24 hours</a><a class="{'active' if horizon=='7d' else ''}" href="/dashboard?horizon=7d">Next 7 days</a></nav></header>
<div class="note">BUY/SELL appears only when the engine marked the candidate <b>TRADE</b>. Otherwise it stays <b>WAIT</b>. Entry area is a display zone of ±10% of the modeled stop distance around the current strategy entry; it is not yet separately optimized by backtest.</div>
{''.join(cards)}{empty}</div></body></html>""")


def signal_detail_page(request: Request, signal_id: int):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    row=fetch_signal_by_id(signal_id)
    if not row:
        return HTMLResponse("Signal not found",status_code=404)
    lo,hi=_entry_zone(row)
    label=_trade_label(row)
    symbol=html.escape(str(row.get("symbol") or ""))
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{symbol} signal</title><style>
body{{background:#081018;color:#edf2f7;font-family:Arial,sans-serif;margin:0}}.wrap{{max-width:900px;margin:auto;padding:25px}}.panel{{background:#111c27;border:1px solid #26394c;border-radius:16px;padding:22px}}h1{{margin-top:0}}.big{{font-size:28px;font-weight:bold}}.levels{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:18px 0}}.levels div{{background:#0a141e;padding:15px;border-radius:10px}}small{{display:block;color:#8197ab;margin-bottom:4px}}a{{display:inline-block;color:#081018;background:#edf2f7;text-decoration:none;padding:11px 14px;border-radius:9px;font-weight:bold;margin:8px 8px 0 0}}.back{{background:#26394c;color:white}}.riskbar{{height:90px;position:relative;margin:30px 25px}}.riskline{{position:absolute;top:38px;left:0;right:0;height:5px;background:#4a647a}}.marker{{position:absolute;top:16px;transform:translateX(-50%);text-align:center;font-size:11px}}.marker:after{{content:'';display:block;width:3px;height:45px;background:#d7e0e8;margin:auto}}.marker small{{white-space:nowrap}}
</style></head><body><div class="wrap"><div class="panel"><h1>{symbol} — {html.escape(str(row.get('timeframe') or ''))}</h1><div class="big">{label} · {html.escape(str(row.get('direction') or ''))}</div>
<div class="levels"><div><small>ENTRY AREA</small><b>{_price(lo)} – {_price(hi)}</b></div><div><small>STOP LOSS</small><b>{_price(row.get('stop_loss'))}</b></div><div><small>TARGET 1</small><b>{_price(row.get('target_1'))}</b></div><div><small>TARGET 2</small><b>{_price(row.get('target_2'))}</b></div></div>{_risk_visual(row)}
<p>Evidence score: <b>{float(row.get('evidence_score') or 0):.0f}</b> · Risk/reward: <b>{float(row.get('risk_reward') or 0):.2f}</b> · Regime: <b>{html.escape(str(row.get('market_regime') or 'UNKNOWN'))}</b></p>
<p>{html.escape(str(row.get('reasoning') or ''))}</p><a target="_blank" rel="noopener" href="{html.escape(_tv_url(row))}">Open live TradingView chart</a><a class="back" href="/dashboard?horizon={html.escape(str(row.get('timeframe') or '24h'))}">Back to rankings</a></div></div></body></html>""")

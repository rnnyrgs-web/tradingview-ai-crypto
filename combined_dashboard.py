import html

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPPORTUNITY_HORIZONS
from dashboard import _authorized
from db import fetch_ranked_opportunities
from paper_db import fetch_all_paper_trades, fetch_open_paper_trades
from paper_trading import _liquidation_mark, paper_status
from cross_asset_research import fetch_cross_asset_leaders


def _price(value):
    try:
        x=float(value)
    except (TypeError,ValueError):
        return "—"
    if x>=1000:return f"{x:,.2f}"
    if x>=1:return f"{x:,.4f}"
    if x>=.01:return f"{x:.6f}"
    return f"{x:.8f}"


def _money(value):
    try:return f"${float(value):,.2f}"
    except (TypeError,ValueError):return "—"


def _signed_money(value):
    try:x=float(value)
    except (TypeError,ValueError):return "—"
    return f"{'+$' if x>=0 else '-$'}{abs(x):,.2f}"


def _pct(entry,value):
    try:e=float(entry or 0);v=float(value or 0)
    except (TypeError,ValueError):return None
    return (v/e-1)*100 if e>0 and v>0 else None


def _duration(row):
    h=str(row.get("horizon") or row.get("timeframe") or "").lower()
    return {"6h":"1–6 hours","12h":"6–12 hours","24h":"12–24 hours","48h":"1–2 days","72h":"2–3 days","7d":"3–7 days"}.get(h,"Variable")


def _cal(row):
    c=row.get("calibration") if isinstance(row,dict) else None
    if not isinstance(c,dict):return {"ready":False,"precision":None,"samples":0,"minimum":30,"raw":0}
    try:n=max(0,int(c.get("independent_samples") or c.get("samples") or 0))
    except (TypeError,ValueError):n=0
    try:m=max(1,int(c.get("minimum_samples") or 30))
    except (TypeError,ValueError):m=30
    try:raw=max(0,int(c.get("raw_matching_rows") or 0))
    except (TypeError,ValueError):raw=0
    ready=bool(c.get("ready"))
    try:p=float(c.get("empirical_precision")) if ready and c.get("empirical_precision") is not None else None
    except (TypeError,ValueError):p=None
    return {"ready":ready,"precision":p,"samples":n,"minimum":m,"raw":raw}


def _crypto_rows():
    rows=[]
    for h in OPPORTUNITY_HORIZONS:
        rows.extend(fetch_ranked_opportunities(horizon=h,limit=20))
    best={}
    for r in rows:
        symbol=str(r.get("symbol") or "").upper()
        if not symbol:continue
        move=abs(_pct(r.get("entry_price"),r.get("target_2")) or 0)
        cal=_cal(r);score=(1 if str(r.get("action") or "").upper()=="TRADE" else 0,float(cal["precision"] or 0),float(r.get("evidence_score") or 0),move)
        if symbol not in best or score>best[symbol][0]:best[symbol]=(score,r)
    return [x[1] for x in best.values()]


def _paper_snapshot():
    try:status=paper_status();opens=fetch_open_paper_trades("default");all_trades=fetch_all_paper_trades("default")
    except Exception:return {"status":{},"positions":[],"closed":[],"open_pnl":None,"total_pnl":None,"equity":None,"win_rate":None}
    positions=[];complete=True
    for t in opens:
        p=dict(t)
        try:
            entry=float(p.get("entry_price") or 0);qty=float(p.get("quantity") or 0);notional=float(p.get("notional_usd") or 0);side=str(p.get("direction") or "").upper();fill,_=_liquidation_mark(p)
            pnl=(float(fill)-entry)*qty
            if side=="SHORT":pnl=-pnl
            p.update({"last_price":float(fill),"live_pnl":pnl,"live_pnl_pct":pnl/notional*100 if notional>0 else 0})
        except Exception:
            complete=False;p.update({"last_price":None,"live_pnl":None,"live_pnl_pct":None})
        positions.append(p)
    starting=float(status.get("starting_capital_usd") or 100000);realized=float(status.get("realized_pnl_usd") or 0)
    open_pnl=sum(float(p.get("live_pnl") or 0) for p in positions) if complete else None
    total_pnl=realized+open_pnl if open_pnl is not None else None;equity=starting+total_pnl if total_pnl is not None else None
    closed=[t for t in all_trades if str(t.get("status") or "").upper()=="CLOSED"];closed.sort(key=lambda x:str(x.get("closed_at") or ""),reverse=True)
    ct=int(status.get("closed_trades") or 0);wins=int(status.get("wins") or 0)
    return {"status":status,"positions":positions,"closed":closed[:8],"open_pnl":open_pnl,"total_pnl":total_pnl,"equity":equity,"win_rate":wins/ct*100 if ct else None}


def _market_rows(crypto,cross):
    out=[]
    for r in crypto:
        move=_pct(r.get("entry_price"),r.get("target_2"))
        if move is None:continue
        cal=_cal(r)
        out.append({"kind":"CRYPTO","symbol":str(r.get("symbol") or "").upper(),"asset_class":"CRYPTO","direction":str(r.get("direction") or "").upper(),"expected_move":abs(move),"signed_move":move,"duration":_duration(r),"entry":r.get("entry_price"),"target":r.get("target_2"),"evidence":float(r.get("evidence_score") or 0),"validation":cal,"action":str(r.get("action") or "WAIT").upper(),"signal_id":int(r.get("id") or 0),"rank_score":abs(move)*(0.5+float(r.get("evidence_score") or 0)/100)})
    for r in cross:
        try:move=abs(float(r.get("expected_move_pct") or 0));acc=float(r.get("backtest_accuracy") or 0);score=float(r.get("research_score") or 0)
        except (TypeError,ValueError):continue
        out.append({"kind":"RESEARCH","symbol":str(r.get("symbol") or "").upper(),"asset_class":str(r.get("asset_class") or "OTHER"),"direction":str(r.get("direction") or "").upper(),"expected_move":move,"signed_move":move if str(r.get("direction") or "").upper()=="LONG" else -move,"duration":f"~{int(r.get('horizon_days') or 5)} trading days","entry":r.get("entry_price"),"target":None,"evidence":acc*100,"validation":{"ready":False,"precision":acc,"samples":int(r.get("backtest_samples") or 0),"minimum":0,"raw":int(r.get("backtest_samples") or 0)},"action":"RESEARCH","signal_id":0,"rank_score":score})
    out.sort(key=lambda x:(x["expected_move"],x["rank_score"]),reverse=True)
    return out[:30]


def combined_dashboard_page(request:Request,horizon:str="all"):
    if not _authorized(request):return RedirectResponse("/dashboard/login",status_code=303)
    crypto=_crypto_rows()
    try:cross=fetch_cross_asset_leaders(30)
    except Exception:cross=[]
    markets=_market_rows(crypto,cross)
    paper=_paper_snapshot();ps=paper["status"]
    validated=sum(1 for r in crypto if _cal(r)["precision"] is not None)
    strong=sum(1 for r in markets if r["expected_move"]>=100)
    total_pnl_cls="gain" if paper["total_pnl"] is not None and paper["total_pnl"]>=0 else "loss"
    open_pnl_cls="gain" if paper["open_pnl"] is not None and paper["open_pnl"]>=0 else "loss"
    total_pnl_text=_signed_money(paper["total_pnl"]) if paper["total_pnl"] is not None else "UNVERIFIED"
    open_pnl_text=_signed_money(paper["open_pnl"]) if paper["open_pnl"] is not None else "UNVERIFIED"
    equity_text=_money(paper["equity"]) if paper["equity"] is not None else _money(ps.get("equity_usd"))
    win_rate=f"{paper['win_rate']:.1f}%" if paper["win_rate"] is not None else "—"

    trade_rows=[]
    for p in paper["positions"]:
        pnl=p.get("live_pnl");cls="gain" if pnl is not None and float(pnl)>=0 else "loss";side=str(p.get("direction") or "").upper()
        trade_rows.append(f"<tr><td><b>{html.escape(str(p.get('symbol') or ''))}</b></td><td><span class='side {'long' if side=='LONG' else 'short'}'>{side}</span></td><td>{_money(p.get('notional_usd'))}</td><td>{_price(p.get('entry_price'))}</td><td>{_price(p.get('last_price'))}</td><td class='{cls}'><b>{_signed_money(pnl) if pnl is not None else 'UNVERIFIED'}</b><small>{float(p.get('live_pnl_pct') or 0):+.2f}%</small></td><td class='stop'>{_price(p.get('stop_loss'))}</td><td class='target'>{_price(p.get('target_price'))}</td><td><span class='status active'>OPEN PAPER</span></td></tr>")
    trade_table="".join(trade_rows) or "<tr><td colspan='9' class='empty'>No open paper trades right now.</td></tr>"

    rows=[]
    for i,r in enumerate(markets,1):
        side=r["direction"];sidecls="long" if side=="LONG" else "short";cal=r["validation"];kind=r["kind"]
        if kind=="CRYPTO":
            vtxt=f"{float(cal['precision'])*100:.0f}%" if cal["precision"] is not None else "LEARNING";vsub=f"N={cal['samples']}/{cal['minimum']} independent · raw={cal['raw']}" if cal["precision"] is None else f"N={cal['samples']} independent · raw={cal['raw']}";status="ACTIONABLE" if r["action"]=="TRADE" else "WATCH";target=_price(r["target"]);click=f" onclick=\"location.href='/dashboard/signal/{r['signal_id']}'\"" if r["signal_id"] else ""
        else:
            vtxt=f"{float(cal['precision'])*100:.0f}% hist";vsub=f"{cal['samples']} historical 5d tests · research only";status="RESEARCH";target="—";click=""
        rows.append(f"<tr class='signal-row' data-search='{html.escape((r['symbol']+' '+r['asset_class']).lower())}'{click}><td>{i}</td><td><b>{html.escape(r['symbol'])}</b><small>{html.escape(r['asset_class'])}</small></td><td><span class='tag'>{kind}</span></td><td><span class='side {sidecls}'>{side}</span></td><td><b>{r['expected_move']:.1f}%</b><small>{r['signed_move']:+.1f}% directional</small></td><td>{html.escape(r['duration'])}</td><td>{_price(r['entry'])}</td><td class='target'>{target}</td><td><b>{vtxt}</b><small>{vsub}</small></td><td><span class='status {'active' if status=='ACTIONABLE' else 'watch'}'>{status}</span></td></tr>")
    market_table="".join(rows) or "<tr><td colspan='10' class='empty'>No ranked opportunities available.</td></tr>"

    closed=[]
    for t in paper["closed"]:
        pnl=t.get("pnl_usd");cls="gain" if pnl is not None and float(pnl)>=0 else "loss"
        closed.append(f"<tr><td><b>{html.escape(str(t.get('symbol') or ''))}</b></td><td>{html.escape(str(t.get('direction') or ''))}</td><td>{_price(t.get('entry_price'))}</td><td>{_price(t.get('exit_price'))}</td><td>{html.escape(str(t.get('exit_reason') or '—'))}</td><td class='{cls}'><b>{_signed_money(pnl)}</b></td></tr>")
    closed_table="".join(closed) or "<tr><td colspan='6' class='empty'>No closed paper trades yet.</td></tr>"

    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='60'><title>Market Opportunity Engine</title><style>
*{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--line:#173247;--muted:#7f9aaf;--text:#edf7ff;--green:#35dd91;--red:#ff6674;--blue:#2779ff}}body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740,#06111b 34%,#050d15);color:var(--text);font-family:Inter,Arial,sans-serif}}.shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}.top{{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:14px}}h1{{margin:0;font-size:25px}}.sub{{font-size:12px;color:#91a8b9;margin-top:4px}}.live{{color:var(--green);font-size:12px}}input{{width:360px;max-width:45vw;background:#07131e;border:1px solid #1b3448;color:#fff;border-radius:10px;padding:11px 13px}}.cards{{display:grid;grid-template-columns:repeat(8,minmax(135px,1fr));gap:9px;margin-bottom:14px}}.card,.panel{{background:linear-gradient(180deg,#0b1b29,#08141f);border:1px solid #19344a;border-radius:12px}}.card{{padding:13px 14px}}.label{{font-size:10px;color:#8ca5b8}}.value{{font-size:23px;font-weight:900;margin-top:5px}}.hint{{font-size:10px;color:#7892a6;margin-top:3px}}.gain{{color:var(--green)}}.loss{{color:var(--red)}}.panel{{padding:14px;margin-bottom:14px}}.head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}}.title{{font-size:20px;font-weight:900}}.scan{{font-size:11px;color:#91a8b9}}.tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1200px;background:#07131e}}th{{text-align:left;color:#829db2;font-size:10px;padding:10px;border-bottom:1px solid #1b3a51}}td{{padding:10px;border-bottom:1px solid #10283a;font-size:12px;white-space:nowrap}}tbody tr.signal-row{{cursor:pointer}}tbody tr:hover{{background:#0c1d2a}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}.side,.status,.tag{{display:inline-block;border-radius:7px;padding:5px 8px;font-size:10px;font-weight:900}}.side.long{{background:#0c3527;color:#4de3a0}}.side.short{{background:#3a1720;color:#ff7c87}}.status.active{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.tag{{background:#102a42;color:#7fc2ff}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.empty{{padding:24px;text-align:center;color:#91a8b9}}.note{{color:#7690a4;font-size:11px;line-height:1.45;margin-top:9px}}a{{color:#9ecbff}}@media(max-width:1300px){{.cards{{grid-template-columns:repeat(4,1fr)}}}}@media(max-width:760px){{.shell{{padding:12px}}.top{{flex-direction:column;align-items:flex-start}}input{{width:100%;max-width:none}}.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class='shell'><div class='top'><div><h1>Market Opportunity Engine <span class='live'>● LIVE</span></h1><div class='sub'>Crypto + stocks + ETFs + indices + FX + rates + commodities research · dashboard shows only the strongest ranked moves</div></div><input id='search' placeholder='Search any displayed asset...'></div>
<div class='cards'><div class='card'><div class='label'>DISPLAYED LEADERS</div><div class='value'>{len(markets)}</div><div class='hint'>highest expected moves only</div></div><div class='card'><div class='label'>CRYPTO UNIVERSE</div><div class='value'>{len(crypto)}</div><div class='hint'>best current crypto per asset</div></div><div class='card'><div class='label'>CROSS-ASSET RESEARCH</div><div class='value'>{len(cross)}</div><div class='hint'>latest non-crypto leaders</div></div><div class='card'><div class='label'>VALIDATED CRYPTO</div><div class='value'>{validated}</div><div class='hint'>forward calibration ready</div></div><div class='card'><div class='label'>OPEN PAPER TRADES</div><div class='value'>{len(paper['positions'])}</div><div class='hint'>system positions now</div></div><div class='card'><div class='label'>TOTAL P&L</div><div class='value {total_pnl_cls}'>{total_pnl_text}</div><div class='hint'>realized + open</div></div><div class='card'><div class='label'>WIN RATE / PF</div><div class='value'>{win_rate}</div><div class='hint'>PF {float(ps.get('profit_factor') or 0):.2f}</div></div><div class='card'><div class='label'>ACCOUNT / DD</div><div class='value'>{equity_text}</div><div class='hint'>DD {float(ps.get('max_drawdown_pct') or 0):.2f}% · 2×+ {strong}</div></div></div>
<div class='panel'><div class='head'><div class='title'>Open System Trades & P&L</div><div class='scan'>Paper simulation only · Open P&L <b class='{open_pnl_cls}'>{open_pnl_text}</b> · Realized {_signed_money(ps.get('realized_pnl_usd'))}</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>LIVE EXIT MARK</th><th>OPEN P&L</th><th>STOP</th><th>TARGET</th><th>STATUS</th></tr></thead><tbody>{trade_table}</tbody></table></div><div class='note'>These are the system's actual paper positions. No real broker is connected and no real-money orders are placed.</div></div>
<div class='panel'><div class='head'><div class='title'>Top Expected Moves Across Markets</div><div class='scan'>Ranked by expected move; research-only non-crypto rows cannot become trades</div></div><div class='tablewrap'><table><thead><tr><th>#</th><th>ASSET</th><th>TYPE</th><th>DIRECTION</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>VALIDATION / STUDY</th><th>STATUS</th></tr></thead><tbody>{market_table}</tbody></table></div><div class='note'>Crypto validation N counts only non-overlapping fully resolved horizon windows, so repeated 15-minute scans do not inflate confidence. Raw matching rows can be much larger than N. Cross-asset historical accuracy is shown as research evidence only, not as live-trade confidence.</div></div>
<div class='panel'><div class='head'><div class='title'>Recent Closed Paper Trades</div><div class='scan'>{int(ps.get('closed_trades') or 0)} closed · {int(ps.get('wins') or 0)} wins · {int(ps.get('losses') or 0)} losses</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>REASON</th><th>REALIZED P&L</th></tr></thead><tbody>{closed_table}</tbody></table></div></div></div><script>const q=document.getElementById('search');const rs=[...document.querySelectorAll('.signal-row')];q.addEventListener('input',()=>{{const s=q.value.trim().toLowerCase();rs.forEach(r=>r.style.display=!s||(r.dataset.search||'').includes(s)?'':'none')}});</script></body></html>""")

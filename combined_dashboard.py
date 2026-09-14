from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard import _authorized


def combined_dashboard_page(request: Request, horizon: str = "all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    # The user-facing dashboard is intentionally horizon-agnostic. Internal horizon
    # buckets still exist for research/calibration, but they are not exposed as tabs.
    signal_src = "/dashboard/signals?horizon=all"

    return HTMLResponse(f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crypto Signals</title>
<style>
*{{box-sizing:border-box}}
:root{{--bg:#06111b;--panel:#091723;--line:#183247;--muted:#7f9aaf;--text:#edf7ff;--blue:#2779ff;--green:#35dd91;--red:#ff6674;--amber:#f0c94f}}
body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740 0,#06111b 34%,#050d15 100%);color:var(--text);font-family:Inter,Arial,sans-serif;min-height:100vh}}
.shell{{max-width:1900px;margin:auto;padding:18px 20px 30px}}
.topbar{{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:14px}}
.brand{{display:flex;align-items:center;gap:12px}}.logo{{font-size:30px;color:#2b9cff}}h1{{font-size:25px;margin:0}}.live{{font-size:12px;color:var(--green);font-weight:900;margin-left:6px}}.sub{{font-size:12px;color:#94aabd;margin-top:3px}}
.search{{min-width:360px;max-width:520px;width:34%;background:#07131e;border:1px solid #1b3448;color:white;border-radius:10px;padding:12px 14px;outline:none}}
.cards{{display:grid;grid-template-columns:repeat(6,minmax(145px,1fr));gap:10px;margin-bottom:14px}}.card{{background:linear-gradient(180deg,#0b1b29,#091621);border:1px solid #19344a;border-radius:12px;padding:14px 16px}}.label{{font-size:10px;color:#8ca5b8;letter-spacing:.05em}}.value{{font-size:27px;font-weight:900;margin-top:6px}}.hint{{font-size:10px;color:#7892a6;margin-top:3px}}
.filters{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}}button.filter,.paper-toggle{{background:#081520;color:#dce8f2;border:1px solid #25445b;border-radius:9px;padding:9px 13px;font-weight:800;cursor:pointer}}button.filter.active{{background:linear-gradient(180deg,#337fff,#2169eb);border-color:#4c91ff;color:white}}
.panel{{background:rgba(6,17,27,.86);border:1px solid #163247;border-radius:13px;padding:14px;box-shadow:0 20px 70px rgba(0,0,0,.20)}}.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}}.panel-title{{font-size:21px;font-weight:900}}.scan{{font-size:11px;color:#91a8b9}}.scan b{{color:var(--green)}}
.signals{{width:100%;height:950px;border:0;background:transparent;display:block}}
.paper-wrap{{display:none;margin-top:14px}}.paper{{width:100%;height:720px;border:1px solid #183247;border-radius:12px;background:#081018}}.paper-row{{display:flex;justify-content:flex-end;margin-top:10px}}
.foot{{font-size:10px;color:#668296;margin-top:10px}}
@media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.search{{min-width:260px;width:45%}}}}
@media(max-width:700px){{.shell{{padding:12px}}.topbar{{align-items:flex-start;flex-direction:column}}.search{{width:100%;min-width:0}}.cards{{grid-template-columns:repeat(2,1fr)}}.value{{font-size:22px}}.signals{{height:1100px}}}}
</style>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="brand"><div class="logo">▥</div><div><h1>Crypto Signals <span class="live">● LIVE</span></h1><div class="sub">Unified opportunity board · any move size · any expected duration · 24/7</div></div></div>
    <input id="search" class="search" placeholder="Search any coin (BTC, XRP, PONS...)" autocomplete="off">
  </div>

  <div class="cards">
    <div class="card"><div class="label">TOTAL OPPORTUNITIES</div><div class="value" id="total">—</div><div class="hint">current unified signals</div></div>
    <div class="card"><div class="label">HIGH CONFIDENCE</div><div class="value" id="high">—</div><div class="hint">verified ≥65% forward accuracy</div></div>
    <div class="card"><div class="label">STRONG MOVES</div><div class="value" id="strong">—</div><div class="hint">100%+ expected move</div></div>
    <div class="card"><div class="label">TRADE SETUPS</div><div class="value" id="active">—</div><div class="hint">currently actionable</div></div>
    <div class="card"><div class="label">AVG EVIDENCE</div><div class="value" id="evidence">—</div><div class="hint">signal strength / 100</div></div>
    <div class="card"><div class="label">REFRESH</div><div class="value">60s</div><div class="hint">automatic update</div></div>
  </div>

  <div class="filters">
    <button class="filter active" data-filter="all">✧ All Signals</button>
    <button class="filter" data-filter="high">★ High Confidence</button>
    <button class="filter" data-filter="strong">🚀 Strong Moves (2×+)</button>
    <button class="filter" data-filter="active">◉ Trade Setups</button>
    <button class="filter" data-filter="long">↗ Top Bullish</button>
    <button class="filter" data-filter="short">↘ Top Bearish</button>
  </div>

  <div class="panel">
    <div class="panel-head"><div class="panel-title">Live Crypto Signals</div><div class="scan"><b>●</b> Scanning internal research timeframes continuously · displaying one unified opportunity view</div></div>
    <iframe id="signals" class="signals" src="{signal_src}" title="crypto signals"></iframe>
    <div class="foot">Fixed 6h / 12h / 24h / 48h / 72h / 7d buckets are internal research mechanics only. The display shows expected move and estimated duration directly.</div>
  </div>

  <div class="paper-row"><button id="paperToggle" class="paper-toggle">Show paper account</button></div>
  <div id="paperWrap" class="paper-wrap"><iframe class="paper" src="/dashboard/paper" title="live paper account"></iframe></div>
</div>
<script>
const frame=document.getElementById('signals');
const search=document.getElementById('search');
const buttons=[...document.querySelectorAll('.filter')];
let rows=[];let activeFilter='all';
const durationMap={{'6h':'1–6 hours','12h':'6–12 hours','24h':'12–24 hours','48h':'1–2 days','72h':'2–3 days','7d':'3–7 days'}};

function numFromText(t){{const m=(t||'').match(/-?\d+(?:\.\d+)?/);return m?parseFloat(m[0]):0}}
function applyFilters(){{
  const q=(search.value||'').trim().toLowerCase();
  rows.forEach(r=>{{
    const text=(r.dataset.search||'');
    let ok=!q||text.includes(q);
    if(activeFilter==='high')ok=ok&&parseFloat(r.dataset.confidence||'0')>=65;
    if(activeFilter==='strong')ok=ok&&parseFloat(r.dataset.move||'0')>=100;
    if(activeFilter==='active')ok=ok&&r.dataset.status==='active';
    if(activeFilter==='long')ok=ok&&r.dataset.side==='long';
    if(activeFilter==='short')ok=ok&&r.dataset.side==='short';
    r.style.display=ok?'':'none';
  }});
}}

function transformSignals(){{
  try{{
    const d=frame.contentDocument;
    if(!d)return;
    const header=d.querySelector('header');if(header)header.style.display='none';
    const note=d.querySelector('.note');if(note)note.style.display='none';
    const wrap=d.querySelector('.wrap');if(wrap){{wrap.style.padding='0';wrap.style.maxWidth='none';}}
    d.body.style.background='transparent';
    const nav=d.querySelector('nav');if(nav)nav.style.display='none';

    const style=d.createElement('style');style.textContent=`
      body{{background:transparent!important}}
      .tablewrap{{border-color:#173247!important;border-radius:10px!important;background:#07131e!important}}
      table{{min-width:1180px!important;background:#07131e!important}}
      thead{{background:#0b1b28!important}}
      th{{color:#829db2!important;padding:11px 10px!important}}
      td{{padding:11px 10px!important;border-bottom-color:#10283a!important}}
      tbody tr:hover{{background:#0c1d2a!important}}
      .symbol{{font-size:14px!important}}
      .duration{{background:none!important;border:0!important;padding:0!important;color:#c8d8e5!important}}
    `;d.head.appendChild(style);

    const table=d.querySelector('table');if(!table)return;
    const headers=[...table.querySelectorAll('thead th')];
    const hide=[5,6,9];
    hide.forEach(i=>{{if(headers[i])headers[i].style.display='none'}});
    if(headers[1])headers[1].textContent='ASSET';
    if(headers[2])headers[2].textContent='DIRECTION';
    if(headers[3])headers[3].textContent='EST. DURATION';
    if(headers[4])headers[4].textContent='CONFIDENCE';
    if(headers[7])headers[7].textContent='ENTRY';
    if(headers[8])headers[8].textContent='STOP';
    if(headers[10])headers[10].textContent='EXPECTED MOVE / TARGET';
    if(headers[12])headers[12].textContent='STRENGTH';

    rows=[...table.querySelectorAll('tbody tr')];
    let high=0,strong=0,active=0,evidenceSum=0;
    rows.forEach(r=>{{
      const c=[...r.children];hide.forEach(i=>{{if(c[i])c[i].style.display='none'}});
      const symbol=(c[1]?.innerText||'').trim();
      let side=(c[2]?.innerText||'').trim().toUpperCase();
      if(side==='BUY')side='LONG';if(side==='SELL')side='SHORT';if(side==='WAIT')side='WATCH';
      if(c[2])c[2].innerHTML=`<span style="font-weight:900;color:${{side==='LONG'?'#4de3a0':side==='SHORT'?'#ff7c87':'#ead76e'}}">${{side==='LONG'?'↗':side==='SHORT'?'↘':'•'}} ${{side}}</span>`;
      const rawDur=(c[3]?.innerText||'').trim().toLowerCase();if(c[3])c[3].textContent=durationMap[rawDur]||'Variable';
      const confText=(c[4]?.innerText||'');const conf=numFromText(confText);if(conf>=65)high++;
      const moveText=(c[10]?.querySelector('small')?.innerText||'');const move=Math.abs(numFromText(moveText));if(move>=100)strong++;
      const target=(c[10]?.childNodes[0]?.textContent||'').trim();if(c[10])c[10].innerHTML=`<div style="font-weight:900;color:${{moveText.trim().startsWith('-')?'#ff6674':'#35dd91'}}">${{moveText||'—'}}</div><small>${{target?('target '+target):''}}</small>`;
      const ev=numFromText(c[12]?.innerText||'0');evidenceSum+=ev;
      const isActive=side==='LONG'||side==='SHORT';if(isActive)active++;
      r.dataset.search=(symbol+' '+side).toLowerCase();r.dataset.confidence=String(conf);r.dataset.move=String(move);r.dataset.status=isActive?'active':'watch';r.dataset.side=side==='LONG'?'long':side==='SHORT'?'short':'watch';
    }});
    document.getElementById('total').textContent=rows.length;
    document.getElementById('high').textContent=high;
    document.getElementById('strong').textContent=strong;
    document.getElementById('active').textContent=active;
    document.getElementById('evidence').textContent=rows.length?Math.round(evidenceSum/rows.length):0;
    applyFilters();
  }}catch(e){{console.error(e)}}
}}
frame.addEventListener('load',transformSignals);
search.addEventListener('input',applyFilters);
buttons.forEach(b=>b.addEventListener('click',()=>{{activeFilter=b.dataset.filter;buttons.forEach(x=>x.classList.toggle('active',x===b));applyFilters()}}));
const paperToggle=document.getElementById('paperToggle'),paperWrap=document.getElementById('paperWrap');paperToggle.addEventListener('click',()=>{{const open=paperWrap.style.display==='block';paperWrap.style.display=open?'none':'block';paperToggle.textContent=open?'Show paper account':'Hide paper account'}});
</script>
</body>
</html>""")

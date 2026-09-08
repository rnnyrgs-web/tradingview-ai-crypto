from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard import _authorized


def combined_dashboard_page(request: Request, horizon: str = "24h"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    horizon = "7d" if horizon == "7d" else "24h"
    signal_src = f"/dashboard/signals?horizon={quote(horizon)}"
    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crypto Trading Dashboard</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#081018;color:#edf2f7;font-family:Arial,sans-serif}}.wrap{{max-width:1650px;margin:auto;padding:14px}}h1{{margin:0 0 4px;font-size:25px}}.sub{{color:#91a4b7;font-size:13px;margin-bottom:12px}}.section{{margin:12px 0 18px}}.section h2{{font-size:17px;margin:0 0 8px}}iframe{{width:100%;border:1px solid #26394c;border-radius:12px;background:#081018;display:block}}.portfolio{{height:720px}}.signals{{height:1050px}}.note{{font-size:11px;color:#8094a8;margin-top:8px}}@media(max-width:800px){{.wrap{{padding:8px}}.portfolio{{height:920px}}.signals{{height:1100px}}}}
</style></head><body><div class="wrap">
<h1>Crypto Trading Dashboard</h1>
<div class="sub">$100,000 hypothetical AI paper portfolio and ranked crypto signals on the same page.</div>
<div class="section"><h2>💰 $100,000 AI Paper Portfolio</h2><iframe class="portfolio" src="/dashboard/paper" title="$100k paper portfolio"></iframe></div>
<div class="section"><h2>📊 Crypto Signals</h2><iframe class="signals" src="{signal_src}" title="crypto signals"></iframe></div>
<div class="note">Paper trading is hypothetical only. No broker is connected and no real orders can be placed.</div>
</div></body></html>""")

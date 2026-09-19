import html
import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard import _authorized

STATE_PATH = Path(__file__).with_name("money_intelligence") / "dashboard_state.json"


def _load_state():
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("dashboard state must be an object")
        return raw
    except Exception:
        return {
            "schema_version": 1,
            "as_of": None,
            "status": "STATE_UNAVAILABLE",
            "world_money_map": {"summary": "Money Intelligence state is unavailable. No conclusions are being invented."},
            "money_flows": [],
            "opportunities": [],
            "risks": [],
            "causal_chains": [],
            "discoveries": [],
            "changes_since_previous": [],
            "unknowns": ["Dashboard state could not be read."],
            "research_frontier": [],
            "prediction_scorecard": {"frozen": 0, "resolved": 0, "calibration_status": "UNKNOWN"},
            "source_notes": [],
        }


def _esc(value):
    return html.escape(str(value if value is not None else "—"))


def _list_cards(items, empty_message, kind="neutral"):
    if not isinstance(items, list) or not items:
        return f'<div class="empty">{_esc(empty_message)}</div>'
    out = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title") or item.get("asset") or item.get("name") or item.get("flow") or "Untitled"
            body = item.get("summary") or item.get("thesis") or item.get("reason") or item.get("description") or ""
            direction = item.get("action") or item.get("direction") or item.get("status") or ""
            horizon = item.get("horizon") or ""
            confidence = item.get("confidence")
            meta_parts = []
            if direction:
                meta_parts.append(_esc(direction))
            if horizon:
                meta_parts.append(_esc(horizon))
            if confidence is not None:
                meta_parts.append(f"confidence {_esc(confidence)}")
            meta = " · ".join(meta_parts)
            extra = []
            if item.get("invalidation"):
                extra.append(f"<b>Invalidation:</b> {_esc(item.get('invalidation'))}")
            if item.get("source"):
                extra.append(f"<b>Source:</b> {_esc(item.get('source'))}")
            extra_html = f'<p class="small">{"<br>".join(extra)}</p>' if extra else ""
            out.append(
                f'<article class="card {kind}"><h3>{_esc(title)}</h3>'
                f'<div class="meta">{meta}</div><p>{_esc(body)}</p>{extra_html}</article>'
            )
        else:
            out.append(f'<article class="card {kind}"><p>{_esc(item)}</p></article>')
    return "".join(out)


def _metric(label, value):
    return f'<div class="metric"><span>{_esc(label)}</span><strong>{_esc(value)}</strong></div>'


def money_dashboard_page(request: Request):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    state = _load_state()
    world = state.get("world_money_map") if isinstance(state.get("world_money_map"), dict) else {}
    score = state.get("prediction_scorecard") if isinstance(state.get("prediction_scorecard"), dict) else {}
    status = state.get("status") or "UNKNOWN"
    as_of = state.get("as_of") or "Not published yet"

    metrics = "".join([
        _metric("Regime", world.get("regime", "UNKNOWN")),
        _metric("Liquidity", world.get("liquidity", "UNKNOWN")),
        _metric("Credit", world.get("credit", "UNKNOWN")),
        _metric("Policy", world.get("policy", "UNKNOWN")),
        _metric("Risk appetite", world.get("risk_appetite", "UNKNOWN")),
        _metric("Resolved forecasts", score.get("resolved", 0)),
        _metric("Hit rate", f"{score.get('directional_hit_rate'):.1%}" if isinstance(score.get("directional_hit_rate"), (int, float)) else "LEARNING"),
        _metric("Calibration", score.get("calibration_status", "LEARNING")),
    ])

    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>Money Intelligence</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#071019;color:#edf4fb;font-family:Arial,sans-serif}} a{{color:#b9d9ff}}
.wrap{{max-width:1500px;margin:auto;padding:20px}} header{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:14px}}
h1{{margin:0;font-size:28px}} .subtitle{{color:#91a7ba;margin-top:5px;max-width:900px;line-height:1.45}} .nav{{display:flex;gap:8px;flex-wrap:wrap}}
.nav a{{text-decoration:none;border:1px solid #34506a;border-radius:9px;padding:9px 12px}} .nav .active{{background:#e9f3fb;color:#071019}}
.banner{{background:#0e1b27;border:1px solid #28425a;border-radius:12px;padding:13px 15px;margin:14px 0}} .status{{font-weight:800}} .time{{color:#93a7b9;font-size:12px;margin-top:5px}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin:12px 0 18px}} .metric{{background:#0d1721;border:1px solid #203448;border-radius:10px;padding:11px}}
.metric span{{display:block;color:#8399ac;font-size:11px;text-transform:uppercase;letter-spacing:.05em}} .metric strong{{display:block;margin-top:6px;font-size:15px}}
section{{margin:22px 0}} h2{{font-size:18px;margin:0 0 9px}} .section-note{{color:#8298aa;font-size:12px;margin:-3px 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:10px}} .card{{background:#0d1721;border:1px solid #22374a;border-radius:12px;padding:13px}}
.card h3{{margin:0 0 5px;font-size:15px}} .card p{{margin:7px 0;line-height:1.45;color:#cbd8e3}} .meta{{font-size:11px;color:#8ca2b5}} .small{{font-size:11px!important;color:#9db0bf!important}}
.card.good{{border-left:3px solid #3f9b70}} .card.bad{{border-left:3px solid #aa5757}} .card.learn{{border-left:3px solid #657fa0}} .empty{{background:#0d1721;border:1px dashed #2c4358;border-radius:10px;padding:14px;color:#8399ab}}
.world{{font-size:15px;line-height:1.55;color:#dbe6ef}}
.footer{{margin-top:28px;color:#71879a;font-size:11px;border-top:1px solid #17293a;padding-top:13px}}
</style></head><body><div class="wrap">
<header><div><h1>Money Intelligence</h1><div class="subtitle">Independent world · economy · money · credit · capital-flow research. This dashboard does not read or alter crypto signal decisions.</div></div><div class="nav"><a href="/dashboard">Mission Control</a><a href="/dashboard/results">Promising Results</a><a class="active" href="/dashboard/money">Money Intelligence</a></div></header>
<div class="banner"><div class="status">Research state: {_esc(status)}</div><div class="time">As of: {_esc(as_of)} · Refreshes every 5 minutes</div></div>
<div class="metrics">{metrics}</div>
<section><h2>World money map</h2><div class="section-note">Current causal assessment of the monetary, credit and risk regime.</div><div class="banner world">{_esc(world.get('summary') or 'No validated world-money assessment has been published yet.')}</div></section>
<section><h2>Where money is moving</h2><div class="section-note">Observed flows, likely sources and destinations, and the causal reason.</div><div class="grid">{_list_cards(state.get('money_flows'), 'No validated capital-flow observations published yet.', 'learn')}</div></section>
<section><h2>Best current opportunities</h2><div class="section-note">Independent Money Intelligence investment hypotheses. These are not signal-engine outputs.</div><div class="grid">{_list_cards(state.get('opportunities'), 'No evidence-backed opportunity has cleared the Money Intelligence research bar yet.', 'good')}</div></section>
<section><h2>Major risks / capital drains</h2><div class="grid">{_list_cards(state.get('risks'), 'No validated capital-drain thesis published yet.', 'bad')}</div></section>
<section><h2>Causal chains</h2><div class="section-note">Event → economic transmission → money/credit flow → marginal buyer/seller → price/value implication.</div><div class="grid">{_list_cards(state.get('causal_chains'), 'No causal chain has been published yet.', 'learn')}</div></section>
<section><h2>What we learned</h2><div class="grid">{_list_cards(state.get('discoveries'), 'The permanent learning ledger is still in bootstrap.', 'learn')}</div></section>
<section><h2>What changed since the previous report</h2><div class="grid">{_list_cards(state.get('changes_since_previous'), 'No previous Money Intelligence report exists yet.')}</div></section>
<section><h2>Prediction scorecard</h2><div class="banner world">Frozen forecasts: {_esc(score.get('frozen', 0))} · Resolved: {_esc(score.get('resolved', 0))} · Brier score: {_esc(score.get('brier_score'))} · Calibration: {_esc(score.get('calibration_status', 'LEARNING'))}. Skill claims remain unavailable until enough independent forecasts resolve.</div></section>
<section><h2>Unknowns / conflicting evidence</h2><div class="grid">{_list_cards(state.get('unknowns'), 'No explicit unknowns recorded.')}</div></section>
<section><h2>Research frontier</h2><div class="section-note">Highest-information-value unanswered questions the system should attack next.</div><div class="grid">{_list_cards(state.get('research_frontier'), 'No research frontier is currently queued.', 'learn')}</div></section>
<section><h2>Source / evidence notes</h2><div class="grid">{_list_cards(state.get('source_notes'), 'No current source notes published.')}</div></section>
<div class="footer">The Money Intelligence system separates observed facts, inference, hypotheses and forecasts; preserves failed predictions; and treats WAIT / NO EDGE as valid conclusions. It does not authorize real-money execution.</div>
</div></body></html>""")

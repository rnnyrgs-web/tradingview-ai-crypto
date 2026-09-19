"""Human-facing command center for the one-strategy research mission.

This page deliberately fails closed. It never upgrades research evidence into a
validated/profitable claim unless the canonical objective explicitly records a
validated research candidate and the live coordinator evidence is compatible.
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dashboard import _authorized
from signal_development import load_objective


COORDINATOR_STATUS_URL = os.getenv(
    "CONTINUOUS_COORDINATOR_STATUS_URL",
    "https://crypto-continuous-coordinator.onrender.com/health",
).strip()
COORDINATOR_TIMEOUT_SECONDS = 8.0


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "—") -> str:
    raw = str(value or "").strip()
    return raw or fallback


def _bool(value: Any) -> bool:
    return value is True


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _candidate_fingerprint(focus: dict) -> str | None:
    candidate = _dict(focus.get("active_candidate"))
    fingerprint = str(candidate.get("fingerprint_id") or "").strip()
    return fingerprint or None


def build_mission_snapshot(objective: dict, coordinator: dict | None) -> dict:
    """Collapse canonical objective + live coordinator state into fail-closed UI truth."""
    focus = _dict(objective.get("single_strategy_focus"))
    phase = _text(focus.get("lifecycle_phase"), "UNKNOWN")
    candidate = _dict(focus.get("active_candidate"))
    fingerprint = _candidate_fingerprint(focus)

    if not isinstance(coordinator, dict):
        return {
            "mission": _text(objective.get("primary_mission"), "Find one validated after-cost strategy"),
            "strategy_status": "NO VALIDATED STRATEGY YET",
            "phase": phase,
            "candidate_fingerprint": fingerprint,
            "oos_status": "LOCKED",
            "blocker": "coordinator_state_unavailable",
            "coverage": "UNVERIFIED",
            "supported_liquidity_subsets": [],
            "focused_workers": 0,
            "heavy_workers": 0,
            "lightweight_workers": 0,
            "worker_health": "UNVERIFIED",
            "worker_states": {},
            "research_missions": 0,
            "promotion_status": "BLOCKED",
            "broker_status": "UNVERIFIED",
            "trade_authority": False,
            "required_evidence": list(focus.get("required_evidence") or []),
            "gate_status": {},
            "last_screen": None,
            "coordinator_ok": False,
        }

    army = _dict(coordinator.get("worker_army"))
    workers = _dict(army.get("workers"))
    supervisor = _dict(army.get("supervisor"))
    screener = _dict(workers.get("cross-asset-rank-24h"))
    evidence = _dict(screener.get("latest_evidence"))
    selected = _dict(evidence.get("selected_oos"))

    blocker = str(evidence.get("research_blocked_reason") or "").strip()
    if not blocker:
        if fingerprint is None:
            blocker = "screening_for_single_candidate"
        elif phase == "DEEP_VALIDATION" and not _bool(evidence.get("untouched_oos_opened")):
            blocker = "waiting_for_untouched_oos"
        else:
            blocker = "none_reported"

    requested = evidence.get("universe_requested")
    resolved = evidence.get("universe_resolved")
    if requested is None or resolved is None:
        coverage = "UNVERIFIED"
    else:
        coverage = f"{_safe_int(resolved)}/{_safe_int(requested)}"

    oos_opened = _bool(evidence.get("untouched_oos_opened"))
    oos_status = "OPENED" if oos_opened else "LOCKED"
    research_pass = _bool(selected.get("acc002_research_pass"))
    promotion_review = _bool(selected.get("eligible_for_promotion_review"))

    explicit_validation = str(candidate.get("validation_status") or "").strip()
    validated = bool(
        fingerprint
        and explicit_validation == "VALIDATED_RESEARCH_CANDIDATE"
        and research_pass
        and promotion_review
    )
    strategy_status = "VALIDATED RESEARCH CANDIDATE" if validated else "NO VALIDATED STRATEGY YET"
    promotion_status = (
        "RESEARCH VALIDATED — REAL MONEY STILL DISABLED"
        if validated
        else "BLOCKED"
    )

    broker = coordinator.get("broker_connected")
    broker_status = "DISCONNECTED" if broker is False else "UNVERIFIED"
    worker_health = "HEALTHY" if supervisor.get("healthy") is True else "DEGRADED"
    if supervisor.get("healthy") is None:
        worker_health = "UNVERIFIED"

    required = list(focus.get("required_evidence") or [])
    gate_status = {}
    for gate in required:
        if gate == "predeclared_immutable_fingerprint":
            gate_status[gate] = "PASS" if fingerprint else "PENDING"
        elif gate == "positive_after_cost_expectancy":
            gate_status[gate] = "PASS" if research_pass else "PENDING"
        elif gate == "untouched_oos":
            gate_status[gate] = "OPEN" if oos_opened else "LOCKED"
        elif gate == "genuine_forward_paper_validation":
            gate_status[gate] = "PASS" if validated else "PENDING"
        else:
            gate_status[gate] = "PENDING"

    director = _dict(coordinator.get("research_director"))
    missions = director.get("missions") if isinstance(director.get("missions"), list) else []
    worker_states = {name: _text(_dict(row).get("state"), "unknown") for name, row in workers.items()}

    return {
        "mission": _text(objective.get("primary_mission"), "Find one validated after-cost strategy"),
        "strategy_status": strategy_status,
        "phase": phase,
        "candidate_fingerprint": fingerprint,
        "oos_status": oos_status,
        "blocker": blocker,
        "coverage": coverage,
        "supported_liquidity_subsets": list(evidence.get("supported_liquidity_subsets") or []),
        "focused_workers": _safe_int(army.get("worker_count")),
        "heavy_workers": _safe_int(army.get("heavy_worker_count")),
        "lightweight_workers": _safe_int(army.get("lightweight_worker_count")),
        "worker_health": worker_health,
        "worker_states": worker_states,
        "research_missions": len(missions),
        "promotion_status": promotion_status,
        "broker_status": broker_status,
        "trade_authority": _bool(coordinator.get("trade_authority")),
        "required_evidence": required,
        "gate_status": gate_status,
        "last_screen": evidence.get("generated_at") or evidence.get("updated_at_ms"),
        "coordinator_ok": coordinator.get("ok") is True,
    }


def fetch_coordinator_state() -> dict | None:
    if not COORDINATOR_STATUS_URL:
        return None
    try:
        response = httpx.get(
            COORDINATOR_STATUS_URL,
            timeout=COORDINATOR_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def _gate_label(name: str) -> str:
    return {
        "predeclared_immutable_fingerprint": "Immutable fingerprint",
        "positive_after_cost_expectancy": "After-cost expectancy",
        "purged_chronological_validation": "Chronological validation",
        "untouched_oos": "Untouched OOS",
        "cost_stress_and_parameter_stability": "Cost + parameter stability",
        "multiple_testing_control": "Multiple-testing control",
        "genuine_forward_paper_validation": "Forward paper validation",
    }.get(name, name.replace("_", " ").title())


def _badge_class(status: str) -> str:
    normalized = status.upper()
    if normalized in {"PASS", "OPEN", "HEALTHY", "DISCONNECTED"}:
        return "good"
    if normalized in {"LOCKED", "PENDING", "BLOCKED", "UNVERIFIED"}:
        return "warn"
    return "bad"


def mission_control_page(request: Request):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    objective = load_objective()
    coordinator = fetch_coordinator_state()
    snapshot = build_mission_snapshot(objective, coordinator)
    generated = datetime.now(timezone.utc).isoformat()

    fingerprint = snapshot["candidate_fingerprint"] or "NOT FROZEN"
    subsets = snapshot["supported_liquidity_subsets"]
    subset_text = ", ".join(f"Top-{x}" for x in subsets) if subsets else "none"
    blocker = snapshot["blocker"].replace("_", " ")

    gate_cards = "".join(
        f"<div class='gate'><span>{html.escape(_gate_label(gate))}</span>"
        f"<b class='{_badge_class(snapshot['gate_status'].get(gate, 'PENDING'))}'>"
        f"{html.escape(snapshot['gate_status'].get(gate, 'PENDING'))}</b></div>"
        for gate in snapshot["required_evidence"]
    ) or "<div class='empty'>No canonical evidence gates available.</div>"

    worker_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td><span class='pill {_badge_class(state)}'>{html.escape(state.upper())}</span></td></tr>"
        for name, state in sorted(snapshot["worker_states"].items())
    ) or "<tr><td colspan='2' class='empty'>Worker state unavailable.</td></tr>"

    status_class = "good" if snapshot["strategy_status"] == "VALIDATED RESEARCH CANDIDATE" else "warn"
    coordinator_class = "good" if snapshot["coordinator_ok"] else "warn"

    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta http-equiv='refresh' content='60'><title>Strategy Mission Control</title>
<style>
*{{box-sizing:border-box}}:root{{--bg:#071019;--panel:#0b1722;--panel2:#0e1d2a;--line:#1b3448;--text:#eef7ff;--muted:#8ba4b8;--green:#43e39b;--yellow:#ffd86b;--red:#ff7180;--blue:#77bfff}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Arial,sans-serif}}.shell{{max-width:1500px;margin:auto;padding:24px}}.top{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}h1{{margin:0;font-size:28px}}.mission{{color:var(--muted);font-size:13px;max-width:850px;line-height:1.5;margin-top:7px}}.links a{{color:var(--blue);text-decoration:none;margin-left:14px;font-size:12px}}.hero{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;margin-bottom:14px}}.card,.panel{{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:14px}}.card{{padding:16px}}.label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}.value{{font-size:22px;font-weight:900;margin-top:8px}}.sub{{font-size:11px;color:var(--muted);margin-top:6px;line-height:1.45}}.good{{color:var(--green)}}.warn{{color:var(--yellow)}}.bad{{color:var(--red)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}}.panel{{padding:16px;margin-bottom:14px}}.panel h2{{font-size:17px;margin:0 0 12px}}.gates{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.gate{{display:flex;justify-content:space-between;gap:10px;background:#08141e;border:1px solid #173149;border-radius:10px;padding:12px;font-size:12px}}.gate span{{color:#afc2d1}}.gate b{{font-size:10px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #163044;font-size:12px}}th{{color:var(--muted);font-size:10px}}.pill{{font-size:10px;font-weight:800}}.blocker{{border-left:3px solid var(--yellow);padding:12px;background:#211d0e;border-radius:8px;line-height:1.45}}.footer{{font-size:10px;color:#6f899d}}.empty{{color:var(--muted);font-size:12px}}@media(max-width:900px){{.hero,.grid,.gates{{grid-template-columns:1fr 1fr}}}}@media(max-width:600px){{.hero,.grid,.gates{{grid-template-columns:1fr}}.top{{flex-direction:column}}.links a{{margin:0 12px 0 0}}}}
</style></head><body><div class='shell'>
<div class='top'><div><h1>Strategy Mission Control</h1><div class='mission'>{html.escape(snapshot['mission'])}</div></div><div class='links'><a href='/dashboard'>Mission Control</a><a href='/dashboard/results'>Promising Results</a><a href='/dashboard/money'>Money Intelligence</a></div></div>
<div class='hero'>
<div class='card'><div class='label'>Mission status</div><div class='value {status_class}'>{html.escape(snapshot['strategy_status'])}</div><div class='sub'>A strategy is not labelled validated from a pretty backtest. Canonical gates must explicitly pass.</div></div>
<div class='card'><div class='label'>Research phase</div><div class='value'>{html.escape(snapshot['phase'])}</div><div class='sub'>One deep candidate maximum.</div></div>
<div class='card'><div class='label'>Untouched OOS</div><div class='value {_badge_class(snapshot['oos_status'])}'>{html.escape(snapshot['oos_status'])}</div><div class='sub'>Must remain locked during candidate selection.</div></div>
</div>
<div class='grid'>
<div class='card'><div class='label'>Candidate fingerprint</div><div class='value' style='font-size:14px;word-break:break-all'>{html.escape(fingerprint)}</div><div class='sub'>Immutable once frozen.</div></div>
<div class='card'><div class='label'>Data coverage</div><div class='value'>{html.escape(snapshot['coverage'])}</div><div class='sub'>Supported subsets: {html.escape(subset_text)}</div></div>
<div class='card'><div class='label'>Focused workers</div><div class='value'>{snapshot['focused_workers']}</div><div class='sub'>{snapshot['heavy_workers']} heavy · {snapshot['lightweight_workers']} lightweight · {snapshot['research_missions']} research missions</div></div>
<div class='card'><div class='label'>Coordinator / broker</div><div class='value {coordinator_class}'>{html.escape(snapshot['worker_health'])}</div><div class='sub'>Broker: <b class='{_badge_class(snapshot['broker_status'])}'>{html.escape(snapshot['broker_status'])}</b> · trade authority: {str(snapshot['trade_authority']).upper()}</div></div>
</div>
<div class='panel'><h2>Current blocker</h2><div class='blocker'><b>{html.escape(blocker)}</b><div class='sub'>The system must solve or falsify this without weakening evidence thresholds.</div></div></div>
<div class='panel'><h2>Evidence gates</h2><div class='gates'>{gate_cards}</div></div>
<div class='panel'><h2>Focused team activity</h2><table><thead><tr><th>WORKER</th><th>STATE</th></tr></thead><tbody>{worker_rows}</tbody></table></div>
<div class='panel'><h2>Promotion state</h2><div class='value {_badge_class(snapshot['promotion_status'])}' style='font-size:16px'>{html.escape(snapshot['promotion_status'])}</div><div class='sub'>Research validation never grants automatic real-money trading authority.</div></div>
<div class='footer'>Generated {html.escape(generated)} · auto-refresh 60s · fail-closed display · live coordinator source: {'reachable' if coordinator is not None else 'unavailable'}.</div>
</div></body></html>""")

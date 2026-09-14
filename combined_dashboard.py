import html
import math
import os
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPPORTUNITY_HORIZONS
from cross_asset_research import fetch_cross_asset_leaders
from dashboard import _authorized
from db import fetch_ranked_opportunities
from paper_audit import V2_EXECUTION_MODEL
from paper_db import fetch_all_paper_trades, fetch_open_paper_trades
from paper_trading import MAX_SIGNAL_AGE_SECONDS, _liquidation_mark, paper_status

# This is only a historical reference for identifying definitely pre-fix rows.
# It MUST NOT be used to declare rows clean because a GitHub merge is not proof
# that production was already running that commit.
FIX_MERGE_REFERENCE_UTC = "2026-09-14T16:32:18Z"

# Set this only to the VERIFIED production activation timestamp of the #349 fix.
# Until it is configured, the dashboard deliberately refuses to call any
# post-merge trade POST-FIX CLEAN.
VERIFIED_FIX_CUTOVER_UTC = os.getenv("PAPER_GEOMETRY_FIX_CUTOVER_UTC", "").strip()
MIN_FORWARD_CLOSED_TRADES = 30


def _parse_utc(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


_MERGE_REFERENCE_DT = _parse_utc(FIX_MERGE_REFERENCE_UTC)
_VERIFIED_CUTOVER_DT = _parse_utc(VERIFIED_FIX_CUTOVER_UTC)


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _price(value):
    x = _finite(value)
    if x is None or x <= 0:
        return "—"
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:,.4f}"
    if x >= .01:
        return f"{x:.6f}"
    return f"{x:.8f}"


def _money(value):
    x = _finite(value)
    return f"${x:,.2f}" if x is not None else "—"


def _signed_money(value):
    x = _finite(value)
    if x is None:
        return "UNVERIFIED"
    return f"{'+$' if x >= 0 else '-$'}{abs(x):,.2f}"


def _pct(entry, value):
    e = _finite(entry)
    v = _finite(value)
    if e is None or v is None or e <= 0 or v <= 0:
        return None
    return (v / e - 1.0) * 100.0


def _duration(row):
    explicit = str(
        row.get("expected_duration")
        or row.get("expected_move_duration")
        or row.get("duration")
        or ""
    ).strip()
    if explicit:
        return explicit, "model/recorded"
    h = str(row.get("horizon") or row.get("timeframe") or "").lower()
    proxy = {
        "6h": "~1–6 hours",
        "12h": "~6–12 hours",
        "24h": "~12–24 hours",
        "48h": "~1–2 days",
        "72h": "~2–3 days",
        "7d": "~3–7 days",
    }.get(h)
    if proxy:
        return proxy, "forecast-horizon proxy"
    return "Not separately estimated", "unavailable"


def _cal(row):
    c = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(c, dict):
        return {
            "ready": False,
            "precision": None,
            "samples": 0,
            "minimum": 30,
            "raw": 0,
            "allows_live_action": False,
            "restriction_reason": "CALIBRATION_MISSING",
        }
    try:
        n = max(0, int(c.get("independent_samples") or c.get("samples") or 0))
    except (TypeError, ValueError):
        n = 0
    try:
        minimum = max(1, int(c.get("minimum_samples") or 30))
    except (TypeError, ValueError):
        minimum = 30
    try:
        raw = max(0, int(c.get("raw_matching_rows") or 0))
    except (TypeError, ValueError):
        raw = 0
    ready = bool(c.get("ready"))
    precision = _finite(c.get("empirical_precision")) if ready else None
    return {
        "ready": ready,
        "precision": precision,
        "samples": n,
        "minimum": minimum,
        "raw": raw,
        "allows_live_action": bool(c.get("allows_live_action")),
        "restriction_reason": str(c.get("restriction_reason") or ""),
    }


def _freshness(row, now=None):
    generated = _parse_utc(row.get("generated_at"))
    if generated is None:
        return False, None, "timestamp unavailable"
    current = now or datetime.now(timezone.utc)
    age = max(0.0, (current - generated).total_seconds())
    return age <= MAX_SIGNAL_AGE_SECONDS, age, f"{int(age // 60)}m old"


def _measurement_cohort(trade):
    opened = _parse_utc(trade.get("opened_at"))
    if opened is None:
        return "UNVERIFIED"
    if _MERGE_REFERENCE_DT and opened < _MERGE_REFERENCE_DT:
        return "LEGACY"
    if _VERIFIED_CUTOVER_DT is None:
        return "UNVERIFIED"
    if opened < _VERIFIED_CUTOVER_DT:
        return "UNVERIFIED"
    if str(trade.get("execution_model_version") or "") != str(V2_EXECUTION_MODEL):
        return "UNVERIFIED"
    return "POST-FIX CLEAN"


def _closed_metrics(trades):
    ordered = sorted(
        trades,
        key=lambda x: str(x.get("closed_at") or x.get("opened_at") or ""),
    )
    pnls = []
    invalid = 0
    for trade in ordered:
        pnl = _finite(trade.get("pnl_usd"))
        if pnl is None:
            invalid += 1
            continue
        pnls.append(pnl)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    realized = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else None)
    )
    win_rate = len(wins) / len(pnls) * 100 if pnls else None
    expectancy = realized / len(pnls) if pnls else None

    # This is intentionally named realized_sequence_drawdown. It is not a full
    # mark-to-market account drawdown and the dashboard must not present it as one.
    equity = 0.0
    peak = 0.0
    realized_sequence_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        realized_sequence_drawdown = max(realized_sequence_drawdown, peak - equity)

    return {
        "raw_count": len(ordered),
        "count": len(pnls),
        "invalid_count": invalid,
        "complete": invalid == 0,
        "wins": len(wins),
        "losses": len(losses),
        "realized_pnl": realized,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "expectancy": expectancy,
        "realized_sequence_drawdown_usd": realized_sequence_drawdown,
    }


def _empty_paper_snapshot(error=None):
    return {
        "data_ok": False,
        "error": error or "paper data unavailable",
        "status": {},
        "positions": [],
        "clean_closed": [],
        "audit_closed": [],
        "forward": _closed_metrics([]),
        "legacy": _closed_metrics([]),
        "unverified": _closed_metrics([]),
        "forward_positions": [],
        "legacy_positions": [],
        "unverified_positions": [],
        "forward_open_pnl": None,
        "legacy_open_pnl": None,
        "unverified_open_pnl": None,
        "forward_total_pnl": None,
        "mark_failures": 0,
    }


def _paper_snapshot():
    try:
        status = paper_status()
        opens = fetch_open_paper_trades("default")
        all_trades = fetch_all_paper_trades("default")
    except Exception as exc:
        return _empty_paper_snapshot(type(exc).__name__)

    positions = []
    mark_failures = 0
    for trade in opens:
        p = dict(trade)
        try:
            entry = _finite(p.get("entry_price"))
            qty = _finite(p.get("quantity"))
            notional = _finite(p.get("notional_usd"))
            side = str(p.get("direction") or "").upper()
            if entry is None or qty is None or notional is None or entry <= 0 or qty <= 0 or notional <= 0:
                raise ValueError("invalid open-trade economics")
            fill, _ = _liquidation_mark(p)
            fill = _finite(fill)
            if fill is None or fill <= 0:
                raise ValueError("invalid liquidation mark")
            pnl = (fill - entry) * qty
            if side == "SHORT":
                pnl = -pnl
            elif side != "LONG":
                raise ValueError("invalid direction")
            p.update({
                "last_price": fill,
                "live_pnl": pnl,
                "live_pnl_pct": pnl / notional * 100,
                "mark_ok": True,
            })
        except Exception:
            mark_failures += 1
            p.update({
                "last_price": None,
                "live_pnl": None,
                "live_pnl_pct": None,
                "mark_ok": False,
            })
        p["measurement_cohort"] = _measurement_cohort(p)
        positions.append(p)

    closed = [
        dict(t)
        for t in all_trades
        if str(t.get("status") or "").upper() == "CLOSED"
    ]
    for trade in closed:
        trade["measurement_cohort"] = _measurement_cohort(trade)
    closed.sort(key=lambda x: str(x.get("closed_at") or ""), reverse=True)

    clean_closed = [t for t in closed if t["measurement_cohort"] == "POST-FIX CLEAN"]
    legacy_closed = [t for t in closed if t["measurement_cohort"] == "LEGACY"]
    unverified_closed = [t for t in closed if t["measurement_cohort"] == "UNVERIFIED"]
    forward_positions = [p for p in positions if p["measurement_cohort"] == "POST-FIX CLEAN"]
    legacy_positions = [p for p in positions if p["measurement_cohort"] == "LEGACY"]
    unverified_positions = [p for p in positions if p["measurement_cohort"] == "UNVERIFIED"]

    forward = _closed_metrics(clean_closed)
    legacy = _closed_metrics(legacy_closed)
    unverified = _closed_metrics(unverified_closed)

    def _open_sum(rows):
        if any(p.get("mark_ok") is not True for p in rows):
            return None
        return sum(float(p.get("live_pnl") or 0.0) for p in rows)

    forward_open_pnl = _open_sum(forward_positions)
    legacy_open_pnl = _open_sum(legacy_positions)
    unverified_open_pnl = _open_sum(unverified_positions)
    forward_total_pnl = None
    if forward["complete"] and forward_open_pnl is not None:
        forward_total_pnl = forward["realized_pnl"] + forward_open_pnl

    return {
        "data_ok": True,
        "error": None,
        "status": status,
        "positions": positions,
        "clean_closed": clean_closed[:12],
        "audit_closed": [t for t in closed if t["measurement_cohort"] != "POST-FIX CLEAN"][:12],
        "forward": forward,
        "legacy": legacy,
        "unverified": unverified,
        "forward_positions": forward_positions,
        "legacy_positions": legacy_positions,
        "unverified_positions": unverified_positions,
        "forward_open_pnl": forward_open_pnl,
        "legacy_open_pnl": legacy_open_pnl,
        "unverified_open_pnl": unverified_open_pnl,
        "forward_total_pnl": forward_total_pnl,
        "mark_failures": mark_failures,
    }


def _crypto_rows():
    rows = []
    fetch_errors = 0
    for horizon in OPPORTUNITY_HORIZONS:
        try:
            rows.extend(fetch_ranked_opportunities(horizon=horizon, limit=20))
        except Exception:
            fetch_errors += 1
    best = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        move = abs(_pct(row.get("entry_price"), row.get("target_2")) or 0.0)
        cal = _cal(row)
        fresh, _, _ = _freshness(row)
        actionable = str(row.get("action") or "").upper() == "TRADE" and fresh
        score = (
            1 if actionable else 0,
            1 if cal["allows_live_action"] else 0,
            float(cal["precision"] or 0.0),
            float(row.get("evidence_score") or 0.0),
            move,
        )
        if symbol not in best or score > best[symbol][0]:
            best[symbol] = (score, row)
    return [x[1] for x in best.values()], fetch_errors


def _market_rows(crypto, cross):
    out = []
    for row in crypto:
        move = _pct(row.get("entry_price"), row.get("target_2"))
        if move is None:
            continue
        cal = _cal(row)
        fresh, age_seconds, age_text = _freshness(row)
        duration, duration_source = _duration(row)
        action = str(row.get("action") or "WAIT").upper()
        actionable = action == "TRADE" and fresh and cal["allows_live_action"]
        out.append({
            "kind": "CRYPTO",
            "symbol": str(row.get("symbol") or "").upper(),
            "asset_class": "CRYPTO",
            "direction": str(row.get("direction") or "").upper(),
            "expected_move": abs(move),
            "signed_move": move,
            "duration": duration,
            "duration_source": duration_source,
            "entry": row.get("entry_price"),
            "target": row.get("target_2"),
            "evidence": float(row.get("evidence_score") or 0.0),
            "validation": cal,
            "action": action,
            "actionable": actionable,
            "fresh": fresh,
            "age_seconds": age_seconds,
            "age_text": age_text,
            "signal_id": int(row.get("id") or 0),
        })

    for row in cross:
        move = _finite(row.get("expected_move_pct"))
        acc = _finite(row.get("backtest_accuracy"))
        if move is None or acc is None:
            continue
        direction = str(row.get("direction") or "").upper()
        duration = str(row.get("expected_duration") or "").strip()
        if not duration:
            try:
                duration = f"~{int(row.get('horizon_days') or 5)} trading days (study horizon proxy)"
            except (TypeError, ValueError):
                duration = "Not separately estimated"
        out.append({
            "kind": "RESEARCH",
            "symbol": str(row.get("symbol") or "").upper(),
            "asset_class": str(row.get("asset_class") or "OTHER"),
            "direction": direction,
            "expected_move": abs(move),
            "signed_move": abs(move) if direction == "LONG" else -abs(move),
            "duration": duration,
            "duration_source": "historical research",
            "entry": row.get("entry_price"),
            "target": None,
            "evidence": acc * 100.0,
            "validation": {
                "ready": False,
                "precision": acc,
                "samples": int(row.get("backtest_samples") or 0),
                "minimum": 0,
                "raw": int(row.get("backtest_samples") or 0),
                "allows_live_action": False,
            },
            "action": "RESEARCH",
            "actionable": False,
            "fresh": False,
            "age_seconds": None,
            "age_text": "historical study",
            "signal_id": 0,
        })

    # Actionability and independent calibration come before move magnitude.
    out.sort(
        key=lambda r: (
            1 if r["actionable"] else 0,
            1 if r["kind"] == "CRYPTO" and r["validation"].get("ready") else 0,
            float(r["validation"].get("precision") or 0.0),
            float(r["evidence"] or 0.0),
            float(r["expected_move"] or 0.0),
        ),
        reverse=True,
    )
    return out[:30]


def _pf_text(value):
    if value is None:
        return "—"
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}"


def _cohort_class(cohort):
    if cohort == "POST-FIX CLEAN":
        return "clean"
    if cohort == "UNVERIFIED":
        return "unverified"
    return "legacy"


def _outcome_rows(trades):
    rows = []
    for trade in trades:
        pnl = _finite(trade.get("pnl_usd"))
        cls = "gain" if pnl is not None and pnl >= 0 else "loss"
        cohort = trade.get("measurement_cohort") or "UNVERIFIED"
        pnl_text = _signed_money(pnl) if pnl is not None else "INVALID / UNVERIFIED"
        rows.append(
            f"<tr><td><b>{html.escape(str(trade.get('symbol') or ''))}</b></td>"
            f"<td>{html.escape(str(trade.get('direction') or ''))}</td>"
            f"<td>{_price(trade.get('entry_price'))}</td>"
            f"<td>{_price(trade.get('exit_price'))}</td>"
            f"<td>{html.escape(str(trade.get('exit_reason') or '—'))}</td>"
            f"<td class='{cls}'><b>{pnl_text}</b></td>"
            f"<td><span class='cohort {_cohort_class(cohort)}'>{html.escape(cohort)}</span></td></tr>"
        )
    return "".join(rows) or "<tr><td colspan='7' class='empty'>No rows in this cohort yet.</td></tr>"


def combined_dashboard_page(request: Request, horizon: str = "all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    generated_at = datetime.now(timezone.utc)
    crypto, crypto_fetch_errors = _crypto_rows()
    try:
        cross = fetch_cross_asset_leaders(30)
        cross_ok = True
    except Exception:
        cross = []
        cross_ok = False

    markets = _market_rows(crypto, cross)
    paper = _paper_snapshot()
    forward = paper["forward"]
    legacy = paper["legacy"]
    unverified = paper["unverified"]

    integrity_problems = []
    if not paper["data_ok"]:
        integrity_problems.append(f"paper backend unavailable ({paper['error']})")
    if _VERIFIED_CUTOVER_DT is None:
        integrity_problems.append("production #349 cutover timestamp not verified")
    if paper["mark_failures"]:
        integrity_problems.append(f"{paper['mark_failures']} open mark(s) unavailable")
    if forward["invalid_count"]:
        integrity_problems.append(f"{forward['invalid_count']} malformed clean closed row(s)")
    if crypto_fetch_errors:
        integrity_problems.append(f"{crypto_fetch_errors} opportunity feed(s) unavailable")
    if not cross_ok:
        integrity_problems.append("cross-asset research feed unavailable")

    dashboard_verified = not integrity_problems
    view_state = "VERIFIED CURRENT VIEW" if dashboard_verified else "DEGRADED / UNVERIFIED"
    view_cls = "gain" if dashboard_verified else "loss"

    forward_total = paper["forward_total_pnl"]
    forward_win_rate = (
        f"{forward['win_rate']:.1f}%" if forward["win_rate"] is not None and forward["complete"] else "UNVERIFIED"
    )
    forward_expectancy = (
        _signed_money(forward["expectancy"]) if forward["expectancy"] is not None and forward["complete"] else "UNVERIFIED"
    )
    forward_pf = _pf_text(forward["profit_factor"]) if forward["complete"] else "UNVERIFIED"

    preliminary_positive = (
        dashboard_verified
        and forward["complete"]
        and forward["count"] >= MIN_FORWARD_CLOSED_TRADES
        and forward["realized_pnl"] > 0
        and forward["expectancy"] is not None
        and forward["expectancy"] > 0
        and forward["profit_factor"] is not None
        and forward["profit_factor"] > 1.0
    )
    # IMPORTANT: the dashboard is not allowed to self-declare canonical
    # profitability proof from local summary statistics alone. Issue #360's
    # stricter OOS/robustness/cost/forward protocol remains authoritative.
    profitability_state = (
        "PRELIMINARY FORWARD POSITIVE — NOT PROVEN"
        if preliminary_positive
        else "NOT PROVEN YET"
    )
    profitability_cls = "warn"

    trade_rows = []
    for p in paper["positions"]:
        pnl = _finite(p.get("live_pnl"))
        cls = "gain" if pnl is not None and pnl >= 0 else "loss"
        side = str(p.get("direction") or "").upper()
        side_cls = "long" if side == "LONG" else "short"
        cohort = p.get("measurement_cohort") or "UNVERIFIED"
        open_text = _signed_money(pnl) if pnl is not None else "UNVERIFIED"
        pct = _finite(p.get("live_pnl_pct"))
        pct_text = f"{pct:+.2f}%" if pct is not None else "mark unavailable"
        trade_rows.append(
            f"<tr><td><b>{html.escape(str(p.get('symbol') or ''))}</b></td>"
            f"<td><span class='side {side_cls}'>{html.escape(side)}</span></td>"
            f"<td>{_money(p.get('notional_usd'))}</td><td>{_price(p.get('entry_price'))}</td>"
            f"<td>{_price(p.get('last_price'))}</td><td class='{cls}'><b>{open_text}</b><small>{pct_text}</small></td>"
            f"<td class='stop'>{_price(p.get('stop_loss'))}</td><td class='target'>{_price(p.get('target_price'))}</td>"
            f"<td><span class='cohort {_cohort_class(cohort)}'>{html.escape(cohort)}</span></td>"
            f"<td><span class='status {'active' if p.get('mark_ok') else 'bad'}'>{'OPEN PAPER' if p.get('mark_ok') else 'MARK UNVERIFIED'}</span></td></tr>"
        )
    trade_table = "".join(trade_rows) or "<tr><td colspan='10' class='empty'>No open paper trades right now.</td></tr>"

    market_rows = []
    for i, row in enumerate(markets, 1):
        side = row["direction"]
        side_cls = "long" if side == "LONG" else "short"
        cal = row["validation"]
        if row["kind"] == "CRYPTO":
            if cal["precision"] is not None:
                validation = f"{float(cal['precision']) * 100:.0f}% calibration"
            else:
                validation = "LEARNING"
            validation_sub = f"N={cal['samples']}/{cal['minimum']} independent · raw={cal['raw']}"
            if row["actionable"]:
                status = "ACTIONABLE"
                status_cls = "active"
            elif not row["fresh"]:
                status = "STALE / WATCH"
                status_cls = "bad"
            else:
                status = "WATCH"
                status_cls = "watch"
            target = _price(row["target"])
            click = f" onclick=\"location.href='/dashboard/signal/{row['signal_id']}'\"" if row["signal_id"] else ""
        else:
            validation = f"{float(cal['precision']) * 100:.0f}% historical"
            validation_sub = f"{cal['samples']} historical tests · RESEARCH ONLY"
            status = "RESEARCH"
            status_cls = "watch"
            target = "—"
            click = ""
        duration_text = f"{html.escape(row['duration'])}<small>{html.escape(row['duration_source'])}</small>"
        freshness_text = html.escape(row["age_text"])
        market_rows.append(
            f"<tr class='signal-row' data-search='{html.escape((row['symbol'] + ' ' + row['asset_class']).lower())}'{click}>"
            f"<td>{i}</td><td><b>{html.escape(row['symbol'])}</b><small>{html.escape(row['asset_class'])}</small></td>"
            f"<td><span class='tag'>{html.escape(row['kind'])}</span></td><td><span class='side {side_cls}'>{html.escape(side)}</span></td>"
            f"<td><b>{row['expected_move']:.1f}%</b><small>{row['signed_move']:+.1f}% directional</small></td>"
            f"<td>{duration_text}</td><td>{_price(row['entry'])}</td><td class='target'>{target}</td>"
            f"<td><b>{validation}</b><small>{validation_sub}</small></td><td>{freshness_text}</td>"
            f"<td><span class='status {status_cls}'>{status}</span></td></tr>"
        )
    market_table = "".join(market_rows) or "<tr><td colspan='11' class='empty'>No ranked opportunities available.</td></tr>"

    clean_outcomes = _outcome_rows(paper["clean_closed"])
    audit_outcomes = _outcome_rows(paper["audit_closed"])

    calibrated = sum(1 for row in crypto if _cal(row)["ready"])
    big_moves = sum(1 for row in markets if row["expected_move"] >= 100)
    problems_text = " · ".join(html.escape(x) for x in integrity_problems) if integrity_problems else "No dashboard-integrity problems detected in this render."
    cutover_text = VERIFIED_FIX_CUTOVER_UTC or "NOT VERIFIED — clean cohort disabled"

    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='60'><title>Current Trading System</title><style>
*{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--line:#173247;--muted:#7f9aaf;--text:#edf7ff;--green:#35dd91;--red:#ff6674;--yellow:#ffe568}}body{{margin:0;background:#06111b;color:var(--text);font-family:Inter,Arial,sans-serif}}.shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}.top{{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:14px}}h1{{margin:0;font-size:25px}}.sub,.note,.scan,.hint{{color:#91a8b9;line-height:1.45}}.sub{{font-size:12px;margin-top:4px}}.scan,.note{{font-size:11px}}.integrity{{padding:10px 12px;border:1px solid #5a4141;border-radius:10px;margin-bottom:12px;background:#251419}}.integrity.ok{{border-color:#24523e;background:#0b2118}}.statebar,.cards{{display:grid;gap:9px;margin-bottom:12px}}.statebar{{grid-template-columns:repeat(4,minmax(160px,1fr))}}.cards{{grid-template-columns:repeat(5,minmax(150px,1fr))}}.state,.card,.panel{{background:#091723;border:1px solid #19344a;border-radius:12px}}.state,.card{{padding:11px 13px}}.state b{{display:block;font-size:12px}}.state span,.hint{{font-size:10px}}.value{{font-size:21px;font-weight:900;margin-top:5px}}.label{{font-size:10px;color:#8ca5b8}}.panel{{padding:14px;margin-bottom:14px}}.head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}}.title{{font-size:19px;font-weight:900}}.tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1250px;background:#07131e}}th{{text-align:left;color:#829db2;font-size:10px;padding:10px;border-bottom:1px solid #1b3a51}}td{{padding:10px;border-bottom:1px solid #10283a;font-size:12px;white-space:nowrap}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}.side,.status,.tag,.cohort{{display:inline-block;border-radius:7px;padding:5px 8px;font-size:10px;font-weight:900}}.long,.gain{{color:#4de3a0}}.short,.loss{{color:#ff7c87}}.warn{{color:#ffe568}}.status.active,.cohort.clean{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.status.bad,.cohort.unverified{{background:#57202b;color:#ff9eaa}}.cohort.legacy{{background:#352f1a;color:#cbbf8b}}.tag{{background:#102a42;color:#7fc2ff}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.empty{{padding:24px;text-align:center;color:#91a8b9}}input{{width:340px;max-width:45vw;background:#07131e;border:1px solid #1b3448;color:#fff;border-radius:10px;padding:11px}}@media(max-width:1000px){{.cards{{grid-template-columns:repeat(2,1fr)}}.statebar{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:650px){{.top{{flex-direction:column;align-items:flex-start}}.statebar,.cards{{grid-template-columns:1fr}}input{{width:100%;max-width:none}}}}</style></head><body><div class='shell'>
<div class='top'><div><h1>Current Trading System <span class='{view_cls}'>● {view_state}</span></h1><div class='sub'>Generated {generated_at.isoformat()} · paper only · broker disconnected · authenticity fails closed.</div></div><input id='search' placeholder='Search displayed assets...'></div>
<div class='integrity {'ok' if dashboard_verified else ''}'><b>DATA INTEGRITY: {'VERIFIED FOR THIS RENDER' if dashboard_verified else 'DEGRADED / UNVERIFIED'}</b><div class='note'>{problems_text}</div></div>
<div class='statebar'><div class='state'><b>EXECUTION: PAPER ONLY</b><span>No real-money broker authority.</span></div><div class='state'><b>BROKER: DISCONNECTED</b><span>Research/paper execution only.</span></div><div class='state'><b>VERIFIED #349 CUTOVER</b><span>{html.escape(cutover_text)}</span></div><div class='state'><b class='{profitability_cls}'>PROFITABILITY: {profitability_state}</b><span>Canonical #360 proof is stricter than these summary KPIs.</span></div></div>
<div class='cards'>
<div class='card'><div class='label'>CLEAN CLOSED / VALID</div><div class='value'>{forward['count']}</div><div class='hint'>{forward['wins']} wins · {forward['losses']} losses · malformed={forward['invalid_count']}</div></div>
<div class='card'><div class='label'>CLEAN WIN RATE</div><div class='value'>{forward_win_rate}</div><div class='hint'>legacy/unverified cohorts excluded</div></div>
<div class='card'><div class='label'>CLEAN PROFIT FACTOR</div><div class='value'>{forward_pf}</div><div class='hint'>valid realized clean rows only</div></div>
<div class='card'><div class='label'>EXPECTANCY / CLEAN CLOSE</div><div class='value'>{forward_expectancy}</div><div class='hint'>invalid economics block verification</div></div>
<div class='card'><div class='label'>CLEAN REALIZED P&L</div><div class='value'>{_signed_money(forward['realized_pnl']) if forward['complete'] else 'UNVERIFIED'}</div><div class='hint'>closed outcomes only</div></div>
<div class='card'><div class='label'>CLEAN OPEN MARK P&L</div><div class='value'>{_signed_money(paper['forward_open_pnl']) if paper['forward_open_pnl'] is not None else 'UNVERIFIED'}</div><div class='hint'>requires every open liquidation mark</div></div>
<div class='card'><div class='label'>TOTAL MARKED CLEAN P&L</div><div class='value'>{_signed_money(forward_total)}</div><div class='hint'>realized + verified open marks; not proof</div></div>
<div class='card'><div class='label'>REALIZED-SEQUENCE DD</div><div class='value'>{_money(forward['realized_sequence_drawdown_usd'])}</div><div class='hint'>NOT full mark-to-market max drawdown</div></div>
<div class='card'><div class='label'>OPEN PAPER TRADES</div><div class='value'>{len(paper['positions'])}</div><div class='hint'>{len(paper['forward_positions'])} clean · {len(paper['legacy_positions'])} legacy · {len(paper['unverified_positions'])} unverified</div></div>
<div class='card'><div class='label'>CALIBRATION-READY CRYPTO</div><div class='value'>{calibrated}</div><div class='hint'>not equivalent to proven profitability</div></div>
<div class='card'><div class='label'>2×+ RESEARCH / OPPORTUNITIES</div><div class='value'>{big_moves}</div><div class='hint'>magnitude alone grants no actionability</div></div>
</div>
<div class='panel'><div class='head'><div class='title'>Open Paper Trades</div><div class='scan'>mark failures: {paper['mark_failures']}</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>EXECUTABLE EXIT MARK</th><th>OPEN P&L</th><th>STOP</th><th>TARGET</th><th>COHORT</th><th>STATUS</th></tr></thead><tbody>{trade_table}</tbody></table></div></div>
<div class='panel'><div class='head'><div class='title'>Current Opportunities & Research</div><div class='scan'>Actionability/calibration rank before move magnitude; freshness shown explicitly.</div></div><div class='tablewrap'><table><thead><tr><th>#</th><th>ASSET</th><th>TYPE</th><th>DIRECTION</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>VALIDATION / STUDY</th><th>FRESHNESS</th><th>STATUS</th></tr></thead><tbody>{market_table}</tbody></table></div></div>
<div class='panel'><div class='head'><div class='title'>Clean Forward Outcomes</div><div class='scan'>Only verified-cutover + {html.escape(str(V2_EXECUTION_MODEL))} rows may appear here.</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>REASON</th><th>REALIZED P&L</th><th>COHORT</th></tr></thead><tbody>{clean_outcomes}</tbody></table></div></div>
<div class='panel'><div class='head'><div class='title'>Legacy / Unverified Audit History</div><div class='scan'>{legacy['count']} valid legacy closes · {unverified['count']} valid unverified closes · never headline proof.</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>REASON</th><th>REALIZED P&L</th><th>COHORT</th></tr></thead><tbody>{audit_outcomes}</tbody></table></div></div>
</div><script>const q=document.getElementById('search');const rs=[...document.querySelectorAll('.signal-row')];q.addEventListener('input',()=>{{const s=q.value.trim().toLowerCase();rs.forEach(r=>r.style.display=!s||(r.dataset.search||'').includes(s)?'':'none')}});</script></body></html>""")
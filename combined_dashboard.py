import html
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPPORTUNITY_HORIZONS
from dashboard import _authorized
from db import fetch_ranked_opportunities
from paper_db import fetch_all_paper_trades, fetch_open_paper_trades
from paper_trading import _liquidation_mark, paper_status
from cross_asset_research import fetch_cross_asset_leaders

# PR #369 / issue #349 made executable-fill paper geometry trustworthy for
# future trades only. Historical rows remain immutable and visible, but must
# never contaminate the headline forward-profitability score.
POST_FIX_CUTOVER_UTC = "2026-09-14T16:32:19Z"
MIN_FORWARD_CLOSED_TRADES = 30


def _price(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:,.4f}"
    if x >= .01:
        return f"{x:.6f}"
    return f"{x:.8f}"


def _money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _signed_money(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{'+$' if x >= 0 else '-$'}{abs(x):,.2f}"


def _pct(entry, value):
    try:
        e = float(entry or 0)
        v = float(value or 0)
    except (TypeError, ValueError):
        return None
    return (v / e - 1) * 100 if e > 0 and v > 0 else None


def _duration(row):
    explicit = str(
        row.get("expected_duration")
        or row.get("expected_move_duration")
        or row.get("duration")
        or ""
    ).strip()
    if explicit:
        return explicit
    h = str(row.get("horizon") or row.get("timeframe") or "").lower()
    return {
        "6h": "~1–6 hours",
        "12h": "~6–12 hours",
        "24h": "~12–24 hours",
        "48h": "~1–2 days",
        "72h": "~2–3 days",
        "7d": "~3–7 days",
    }.get(h, "Variable / model-estimated")


def _cal(row):
    c = row.get("calibration") if isinstance(row, dict) else None
    if not isinstance(c, dict):
        return {"ready": False, "precision": None, "samples": 0, "minimum": 30, "raw": 0}
    try:
        n = max(0, int(c.get("independent_samples") or c.get("samples") or 0))
    except (TypeError, ValueError):
        n = 0
    try:
        m = max(1, int(c.get("minimum_samples") or 30))
    except (TypeError, ValueError):
        m = 30
    try:
        raw = max(0, int(c.get("raw_matching_rows") or 0))
    except (TypeError, ValueError):
        raw = 0
    ready = bool(c.get("ready"))
    try:
        p = float(c.get("empirical_precision")) if ready and c.get("empirical_precision") is not None else None
    except (TypeError, ValueError):
        p = None
    return {"ready": ready, "precision": p, "samples": n, "minimum": m, "raw": raw}


def _crypto_rows():
    rows = []
    for h in OPPORTUNITY_HORIZONS:
        rows.extend(fetch_ranked_opportunities(horizon=h, limit=20))
    best = {}
    for r in rows:
        symbol = str(r.get("symbol") or "").upper()
        if not symbol:
            continue
        move = abs(_pct(r.get("entry_price"), r.get("target_2")) or 0)
        cal = _cal(r)
        score = (
            1 if str(r.get("action") or "").upper() == "TRADE" else 0,
            float(cal["precision"] or 0),
            float(r.get("evidence_score") or 0),
            move,
        )
        if symbol not in best or score > best[symbol][0]:
            best[symbol] = (score, r)
    return [x[1] for x in best.values()]


def _parse_utc(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


_CUTOVER_DT = _parse_utc(POST_FIX_CUTOVER_UTC)


def _trade_is_post_fix(trade):
    opened = _parse_utc(trade.get("opened_at"))
    return bool(opened and _CUTOVER_DT and opened >= _CUTOVER_DT)


def _closed_metrics(trades):
    ordered = sorted(trades, key=lambda x: str(x.get("closed_at") or x.get("opened_at") or ""))
    pnls = []
    for trade in ordered:
        try:
            pnls.append(float(trade.get("pnl_usd") or 0))
        except (TypeError, ValueError):
            pnls.append(0.0)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    realized = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else None)
    win_rate = len(wins) / len(pnls) * 100 if pnls else None
    avg_win = gross_profit / len(wins) if wins else None
    avg_loss = gross_loss / len(losses) if losses else None
    expectancy = realized / len(pnls) if pnls else None

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return {
        "count": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "realized_pnl": realized,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "max_drawdown_usd": max_drawdown,
    }


def _paper_snapshot():
    try:
        status = paper_status()
        opens = fetch_open_paper_trades("default")
        all_trades = fetch_all_paper_trades("default")
    except Exception:
        return {
            "status": {}, "positions": [], "closed": [],
            "forward": _closed_metrics([]), "legacy": _closed_metrics([]),
            "forward_positions": [], "legacy_positions": [],
            "forward_open_pnl": None, "legacy_open_pnl": None,
            "forward_total_pnl": None,
        }

    positions = []
    for t in opens:
        p = dict(t)
        try:
            entry = float(p.get("entry_price") or 0)
            qty = float(p.get("quantity") or 0)
            notional = float(p.get("notional_usd") or 0)
            side = str(p.get("direction") or "").upper()
            fill, _ = _liquidation_mark(p)
            pnl = (float(fill) - entry) * qty
            if side == "SHORT":
                pnl = -pnl
            p.update({
                "last_price": float(fill),
                "live_pnl": pnl,
                "live_pnl_pct": pnl / notional * 100 if notional > 0 else 0,
            })
        except Exception:
            p.update({"last_price": None, "live_pnl": None, "live_pnl_pct": None})
        p["measurement_cohort"] = "POST-FIX CLEAN" if _trade_is_post_fix(p) else "LEGACY"
        positions.append(p)

    closed = [dict(t) for t in all_trades if str(t.get("status") or "").upper() == "CLOSED"]
    for trade in closed:
        trade["measurement_cohort"] = "POST-FIX CLEAN" if _trade_is_post_fix(trade) else "LEGACY"
    closed.sort(key=lambda x: str(x.get("closed_at") or ""), reverse=True)

    forward_closed = [t for t in closed if t["measurement_cohort"] == "POST-FIX CLEAN"]
    legacy_closed = [t for t in closed if t["measurement_cohort"] == "LEGACY"]
    forward_positions = [p for p in positions if p["measurement_cohort"] == "POST-FIX CLEAN"]
    legacy_positions = [p for p in positions if p["measurement_cohort"] == "LEGACY"]
    forward = _closed_metrics(forward_closed)
    legacy = _closed_metrics(legacy_closed)

    def _open_sum(rows):
        if any(p.get("live_pnl") is None for p in rows):
            return None
        return sum(float(p.get("live_pnl") or 0) for p in rows)

    forward_open_pnl = _open_sum(forward_positions)
    legacy_open_pnl = _open_sum(legacy_positions)
    forward_total_pnl = forward["realized_pnl"] + forward_open_pnl if forward_open_pnl is not None else None

    return {
        "status": status, "positions": positions, "closed": closed[:12],
        "forward": forward, "legacy": legacy,
        "forward_positions": forward_positions, "legacy_positions": legacy_positions,
        "forward_open_pnl": forward_open_pnl, "legacy_open_pnl": legacy_open_pnl,
        "forward_total_pnl": forward_total_pnl,
    }


def _market_rows(crypto, cross):
    out = []
    for r in crypto:
        move = _pct(r.get("entry_price"), r.get("target_2"))
        if move is None:
            continue
        cal = _cal(r)
        out.append({
            "kind": "CRYPTO", "symbol": str(r.get("symbol") or "").upper(), "asset_class": "CRYPTO",
            "direction": str(r.get("direction") or "").upper(), "expected_move": abs(move), "signed_move": move,
            "duration": _duration(r), "entry": r.get("entry_price"), "target": r.get("target_2"),
            "evidence": float(r.get("evidence_score") or 0), "validation": cal,
            "action": str(r.get("action") or "WAIT").upper(), "signal_id": int(r.get("id") or 0),
            "rank_score": abs(move) * (0.5 + float(r.get("evidence_score") or 0) / 100),
        })
    for r in cross:
        try:
            move = abs(float(r.get("expected_move_pct") or 0))
            acc = float(r.get("backtest_accuracy") or 0)
            score = float(r.get("research_score") or 0)
        except (TypeError, ValueError):
            continue
        direction = str(r.get("direction") or "").upper()
        out.append({
            "kind": "RESEARCH", "symbol": str(r.get("symbol") or "").upper(),
            "asset_class": str(r.get("asset_class") or "OTHER"), "direction": direction,
            "expected_move": move, "signed_move": move if direction == "LONG" else -move,
            "duration": str(r.get("expected_duration") or f"~{int(r.get('horizon_days') or 5)} trading days"),
            "entry": r.get("entry_price"), "target": None, "evidence": acc * 100,
            "validation": {"ready": False, "precision": acc, "samples": int(r.get("backtest_samples") or 0), "minimum": 0, "raw": int(r.get("backtest_samples") or 0)},
            "action": "RESEARCH", "signal_id": 0, "rank_score": score,
        })
    out.sort(key=lambda x: (x["expected_move"], x["rank_score"]), reverse=True)
    return out[:30]


def _pf_text(value):
    if value is None:
        return "—"
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}"


def combined_dashboard_page(request: Request, horizon: str = "all"):
    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    crypto = _crypto_rows()
    try:
        cross = fetch_cross_asset_leaders(30)
    except Exception:
        cross = []
    markets = _market_rows(crypto, cross)
    paper = _paper_snapshot()
    forward = paper["forward"]
    legacy = paper["legacy"]

    validated = sum(1 for r in crypto if _cal(r)["precision"] is not None)
    strong = sum(1 for r in markets if r["expected_move"] >= 100)
    forward_total = paper["forward_total_pnl"]
    forward_pnl_cls = "gain" if forward_total is not None and forward_total >= 0 else "loss"
    forward_pnl_text = _signed_money(forward_total) if forward_total is not None else "UNVERIFIED"
    forward_win_rate = f"{forward['win_rate']:.1f}%" if forward["win_rate"] is not None else "LEARNING"
    forward_expectancy = _signed_money(forward["expectancy"]) if forward["expectancy"] is not None else "—"
    forward_pf = _pf_text(forward["profit_factor"])

    proven = (
        forward["count"] >= MIN_FORWARD_CLOSED_TRADES
        and forward["realized_pnl"] > 0
        and forward["expectancy"] is not None and forward["expectancy"] > 0
        and forward["profit_factor"] is not None and forward["profit_factor"] > 1.0
    )
    profitability_state = "PROVEN POSITIVE" if proven else "NOT PROVEN YET"
    profitability_cls = "gain" if proven else "warn"

    trade_rows = []
    for p in paper["positions"]:
        pnl = p.get("live_pnl")
        cls = "gain" if pnl is not None and float(pnl) >= 0 else "loss"
        side = str(p.get("direction") or "").upper()
        cohort = p.get("measurement_cohort") or "LEGACY"
        cohort_cls = "clean" if cohort == "POST-FIX CLEAN" else "legacy"
        trade_rows.append(
            f"<tr><td><b>{html.escape(str(p.get('symbol') or ''))}</b></td>"
            f"<td><span class='side {'long' if side == 'LONG' else 'short'}'>{side}</span></td>"
            f"<td>{_money(p.get('notional_usd'))}</td><td>{_price(p.get('entry_price'))}</td>"
            f"<td>{_price(p.get('last_price'))}</td><td class='{cls}'><b>{_signed_money(pnl) if pnl is not None else 'UNVERIFIED'}</b>"
            f"<small>{float(p.get('live_pnl_pct') or 0):+.2f}%</small></td>"
            f"<td class='stop'>{_price(p.get('stop_loss'))}</td><td class='target'>{_price(p.get('target_price'))}</td>"
            f"<td><span class='cohort {cohort_cls}'>{cohort}</span></td><td><span class='status active'>OPEN PAPER</span></td></tr>"
        )
    trade_table = "".join(trade_rows) or "<tr><td colspan='10' class='empty'>No open paper trades right now.</td></tr>"

    rows = []
    for i, r in enumerate(markets, 1):
        side = r["direction"]
        sidecls = "long" if side == "LONG" else "short"
        cal = r["validation"]
        kind = r["kind"]
        if kind == "CRYPTO":
            vtxt = f"{float(cal['precision']) * 100:.0f}%" if cal["precision"] is not None else "LEARNING"
            vsub = f"N={cal['samples']}/{cal['minimum']} independent · raw={cal['raw']}" if cal["precision"] is None else f"N={cal['samples']} independent · raw={cal['raw']}"
            status = "ACTIONABLE" if r["action"] == "TRADE" else "WATCH"
            target = _price(r["target"])
            click = f" onclick=\"location.href='/dashboard/signal/{r['signal_id']}'\"" if r["signal_id"] else ""
        else:
            vtxt = f"{float(cal['precision']) * 100:.0f}% hist"
            vsub = f"{cal['samples']} historical tests · research only"
            status = "RESEARCH"
            target = "—"
            click = ""
        rows.append(
            f"<tr class='signal-row' data-search='{html.escape((r['symbol'] + ' ' + r['asset_class']).lower())}'{click}>"
            f"<td>{i}</td><td><b>{html.escape(r['symbol'])}</b><small>{html.escape(r['asset_class'])}</small></td>"
            f"<td><span class='tag'>{kind}</span></td><td><span class='side {sidecls}'>{side}</span></td>"
            f"<td><b>{r['expected_move']:.1f}%</b><small>{r['signed_move']:+.1f}% directional</small></td>"
            f"<td>{html.escape(r['duration'])}</td><td>{_price(r['entry'])}</td><td class='target'>{target}</td>"
            f"<td><b>{vtxt}</b><small>{vsub}</small></td>"
            f"<td><span class='status {'active' if status == 'ACTIONABLE' else 'watch'}'>{status}</span></td></tr>"
        )
    market_table = "".join(rows) or "<tr><td colspan='10' class='empty'>No ranked opportunities available.</td></tr>"

    closed = []
    for t in paper["closed"]:
        pnl = t.get("pnl_usd")
        cls = "gain" if pnl is not None and float(pnl) >= 0 else "loss"
        cohort = t.get("measurement_cohort") or "LEGACY"
        cohort_cls = "clean" if cohort == "POST-FIX CLEAN" else "legacy"
        closed.append(
            f"<tr><td><b>{html.escape(str(t.get('symbol') or ''))}</b></td>"
            f"<td>{html.escape(str(t.get('direction') or ''))}</td><td>{_price(t.get('entry_price'))}</td>"
            f"<td>{_price(t.get('exit_price'))}</td><td>{html.escape(str(t.get('exit_reason') or '—'))}</td>"
            f"<td class='{cls}'><b>{_signed_money(pnl)}</b></td>"
            f"<td><span class='cohort {cohort_cls}'>{cohort}</span></td></tr>"
        )
    closed_table = "".join(closed) or "<tr><td colspan='7' class='empty'>No closed paper trades yet.</td></tr>"
    legacy_note = f"{legacy['count']} legacy closed trades retained for audit and excluded from headline KPIs · legacy realized {_signed_money(legacy['realized_pnl'])}."

    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='60'><title>Current Trading System</title><style>
*{{box-sizing:border-box}}:root{{--bg:#06111b;--panel:#091723;--line:#173247;--muted:#7f9aaf;--text:#edf7ff;--green:#35dd91;--red:#ff6674;--blue:#2779ff;--yellow:#ffe568}}body{{margin:0;background:radial-gradient(circle at 18% -10%,#0b2740,#06111b 34%,#050d15);color:var(--text);font-family:Inter,Arial,sans-serif}}.shell{{max-width:1900px;margin:auto;padding:18px 20px 28px}}.top{{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:14px}}h1{{margin:0;font-size:25px}}.sub{{font-size:12px;color:#91a8b9;margin-top:4px;line-height:1.5}}.live{{color:var(--green);font-size:12px}}input{{width:360px;max-width:45vw;background:#07131e;border:1px solid #1b3448;color:#fff;border-radius:10px;padding:11px 13px}}.statebar{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:9px;margin-bottom:12px}}.state{{background:#07131e;border:1px solid #1a3347;border-radius:10px;padding:10px 12px}}.state b{{display:block;font-size:12px;margin-bottom:3px}}.state span{{font-size:10px;color:#829db2}}.cards{{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:9px;margin-bottom:14px}}.card,.panel{{background:linear-gradient(180deg,#0b1b29,#08141f);border:1px solid #19344a;border-radius:12px}}.card{{padding:13px 14px}}.label{{font-size:10px;color:#8ca5b8}}.value{{font-size:22px;font-weight:900;margin-top:5px}}.hint{{font-size:10px;color:#7892a6;margin-top:3px;line-height:1.35}}.gain{{color:var(--green)}}.loss{{color:var(--red)}}.warn{{color:var(--yellow)}}.panel{{padding:14px;margin-bottom:14px}}.head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}}.title{{font-size:20px;font-weight:900}}.scan{{font-size:11px;color:#91a8b9}}.tablewrap{{overflow:auto;border:1px solid #173247;border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1200px;background:#07131e}}th{{text-align:left;color:#829db2;font-size:10px;padding:10px;border-bottom:1px solid #1b3a51}}td{{padding:10px;border-bottom:1px solid #10283a;font-size:12px;white-space:nowrap}}tbody tr.signal-row{{cursor:pointer}}tbody tr:hover{{background:#0c1d2a}}td small{{display:block;color:#738ca0;font-size:10px;margin-top:3px}}.side,.status,.tag,.cohort{{display:inline-block;border-radius:7px;padding:5px 8px;font-size:10px;font-weight:900}}.side.long{{background:#0c3527;color:#4de3a0}}.side.short{{background:#3a1720;color:#ff7c87}}.status.active{{background:#0b5637;color:#6af0b1}}.status.watch{{background:#5a4c0d;color:#ffe568}}.tag{{background:#102a42;color:#7fc2ff}}.cohort.clean{{background:#0b5637;color:#6af0b1}}.cohort.legacy{{background:#352f1a;color:#cbbf8b}}.target{{color:#8cecb9}}.stop{{color:#ffc0c5}}.empty{{padding:24px;text-align:center;color:#91a8b9}}.note{{color:#7690a4;font-size:11px;line-height:1.5;margin-top:9px}}.critical{{border-left:3px solid #ffe568;padding-left:10px}}a{{color:#9ecbff}}@media(max-width:1300px){{.cards{{grid-template-columns:repeat(3,1fr)}}.statebar{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:760px){{.shell{{padding:12px}}.top{{flex-direction:column;align-items:flex-start}}input{{width:100%;max-width:none}}.cards{{grid-template-columns:repeat(2,1fr)}}.statebar{{grid-template-columns:1fr}}}}</style></head><body><div class='shell'>
<div class='top'><div><h1>Current Trading System <span class='live'>● LIVE</span></h1><div class='sub'>Profitability-first view · clean post-#349 forward evidence is primary · legacy paper history remains visible but cannot contaminate the current score.<br>Signals span variable move durations; expected move and estimated duration are displayed separately.</div></div><input id='search' placeholder='Search any displayed asset...'></div>
<div class='statebar'><div class='state'><b>EXECUTION MODE: PAPER ONLY</b><span>No real-money broker authority.</span></div><div class='state'><b>BROKER: DISCONNECTED</b><span>Research and paper execution only.</span></div><div class='state'><b>MEASUREMENT: POST-FIX CLEAN</b><span>Issue #349 geometry repair cutover {POST_FIX_CUTOVER_UTC}.</span></div><div class='state'><b class='{profitability_cls}'>PROFITABILITY: {profitability_state}</b><span>Requires ≥{MIN_FORWARD_CLOSED_TRADES} clean closes plus positive expectancy/PF.</span></div></div>
<div class='cards'><div class='card'><div class='label'>CLEAN FORWARD CLOSED</div><div class='value'>{forward['count']}</div><div class='hint'>{forward['wins']} wins · {forward['losses']} losses · target ≥{MIN_FORWARD_CLOSED_TRADES}</div></div><div class='card'><div class='label'>CLEAN FORWARD WIN RATE</div><div class='value'>{forward_win_rate}</div><div class='hint'>post-fix trades only; legacy 35% excluded</div></div><div class='card'><div class='label'>CLEAN PROFIT FACTOR</div><div class='value'>{forward_pf}</div><div class='hint'>gross wins ÷ gross losses</div></div><div class='card'><div class='label'>EXPECTANCY / CLOSED TRADE</div><div class='value'>{forward_expectancy}</div><div class='hint'>after realized paper execution outcomes</div></div><div class='card'><div class='label'>CLEAN FORWARD P&L</div><div class='value {forward_pnl_cls}'>{forward_pnl_text}</div><div class='hint'>clean realized + clean open P&L</div></div><div class='card'><div class='label'>CLEAN MAX DD</div><div class='value'>{_money(forward['max_drawdown_usd'])}</div><div class='hint'>realized post-fix sequence</div></div><div class='card'><div class='label'>OPEN PAPER TRADES</div><div class='value'>{len(paper['positions'])}</div><div class='hint'>{len(paper['forward_positions'])} clean · {len(paper['legacy_positions'])} legacy</div></div><div class='card'><div class='label'>VALIDATED CRYPTO</div><div class='value'>{validated}</div><div class='hint'>forward calibration-ready opportunity rows</div></div><div class='card'><div class='label'>2×+ MOVE CANDIDATES</div><div class='value'>{strong}</div><div class='hint'>research/opportunity candidates ≥100% expected move</div></div><div class='card'><div class='label'>DISPLAYED LEADERS</div><div class='value'>{len(markets)}</div><div class='hint'>strongest ranked opportunities across current feeds</div></div></div>
<div class='panel'><div class='head'><div class='title'>Open System Trades</div><div class='scan'>Clean open P&L <b>{_signed_money(paper['forward_open_pnl']) if paper['forward_open_pnl'] is not None else 'UNVERIFIED'}</b> · legacy open P&L {_signed_money(paper['legacy_open_pnl']) if paper['legacy_open_pnl'] is not None else 'UNVERIFIED'}</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>LIVE EXIT MARK</th><th>OPEN P&L</th><th>STOP</th><th>TARGET</th><th>MEASUREMENT COHORT</th><th>STATUS</th></tr></thead><tbody>{trade_table}</tbody></table></div><div class='note'>Stops and targets for new paper trades use the immutable signal geometry fixed in #349. Legacy positions remain marked separately.</div></div>
<div class='panel'><div class='head'><div class='title'>Top Expected Moves Across Markets</div><div class='scan'>Expected move magnitude and duration are separate; no fixed-horizon dashboard buckets.</div></div><div class='tablewrap'><table><thead><tr><th>#</th><th>ASSET</th><th>TYPE</th><th>DIRECTION</th><th>EXPECTED MOVE</th><th>EST. DURATION</th><th>ENTRY</th><th>TARGET</th><th>VALIDATION / STUDY</th><th>STATUS</th></tr></thead><tbody>{market_table}</tbody></table></div><div class='note'>Crypto validation uses independent fully resolved samples. Non-crypto historical rows remain research only. A large expected move is not promoted solely because it is large.</div></div>
<div class='panel'><div class='head'><div class='title'>Recent Paper Outcomes</div><div class='scan'>{legacy_note}</div></div><div class='tablewrap'><table><thead><tr><th>ASSET</th><th>SIDE</th><th>ENTRY</th><th>EXIT</th><th>REASON</th><th>REALIZED P&L</th><th>MEASUREMENT COHORT</th></tr></thead><tbody>{closed_table}</tbody></table></div><div class='note critical'><b>Headline profitability uses POST-FIX CLEAN trades only.</b> Historical pre-fix results are audit evidence, not the current system score. The dashboard will say NOT PROVEN YET until enough clean forward evidence exists.</div></div></div><script>const q=document.getElementById('search');const rs=[...document.querySelectorAll('.signal-row')];q.addEventListener('input',()=>{{const s=q.value.trim().toLowerCase();rs.forEach(r=>r.style.display=!s||(r.dataset.search||'').includes(s)?'':'none')}});</script></body></html>""")

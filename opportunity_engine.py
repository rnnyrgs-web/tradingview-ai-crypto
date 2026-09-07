import logging

from config import STRATEGY_VERSION
from db import replace_opportunities
from production_validation import validate_live_strategy

log = logging.getLogger(__name__)


def _entry_zone(plan):
    risk = abs(plan["entry"] - plan["stop"])
    pad = risk * 0.10
    return plan["entry"] - pad, plan["entry"] + pad


def build_opportunities(scan_id, candidates, ai_signals, regime, risk_plan_fn):
    """Persist top-20 24h and 7d rankings from the current scan.

    Direction/rank comes from deterministic multi-timeframe quant evidence.
    BUY/SELL eligibility is fail-closed: even an adversarial AI TRADE review is
    downgraded to WAIT unless the exact strategy identity has completed the
    explicit research-to-live promotion process.
    Evidence score is a ranking score, not a probability.
    """
    ai_map = {}
    for s in ai_signals or []:
        symbol = str(s.get("symbol", "")).upper()
        horizon = str(s.get("horizon", ""))
        if symbol and horizon in {"24h", "7d"}:
            ai_map[(symbol, horizon)] = s

    saved = {}
    for horizon in ("24h", "7d"):
        ranked = []
        for c in candidates:
            hv = c.get("horizons", {}).get(horizon)
            if not hv:
                continue
            q = float(hv.get("score") or 0.0)
            direction = "LONG" if q >= 0 else "SHORT"
            try:
                plan = risk_plan_fn(hv["features"], direction, horizon)
            except Exception as exc:
                log.warning(
                    "Opportunity rejected because risk plan failed: symbol=%s horizon=%s error=%s",
                    c.get("symbol"), horizon, type(exc).__name__,
                )
                continue
            entry_low, entry_high = _entry_zone(plan)
            reviewed = ai_map.get((c["symbol"], horizon), {})
            reviewed_direction = str(reviewed.get("direction", "")).upper()
            action = str(reviewed.get("action", "WAIT")).upper()
            strategy_family = str(reviewed.get("strategy_family", ""))
            validation = validate_live_strategy(c["symbol"], horizon, strategy_family)
            if reviewed_direction != direction or action != "TRADE" or not validation.approved:
                action = "WAIT"
            evidence = float(reviewed.get("evidence_score") or min(99.0, abs(q) / 5.5 * 100.0))
            liquidity_bonus = min(15.0, max(0.0, c.get("activity_score", 0.0)))
            spread_penalty = min(20.0, float(c.get("spread_bps") or 0.0) * 0.35)
            rank_score = abs(q) * 20.0 + liquidity_bonus - spread_penalty
            base_reason = str(reviewed.get("reasoning") or f"Quant rank from multi-timeframe {horizon} evidence; not AI-approved for trade.")
            if not validation.approved:
                base_reason = f"{base_reason} [{validation.status}: {validation.reason}]"
            ranked.append({
                "scan_id": scan_id,
                "horizon": horizon,
                "symbol": c["symbol"],
                "direction": direction,
                "action": action,
                "entry_price": plan["entry"],
                "entry_low": entry_low,
                "entry_high": entry_high,
                "stop_loss": plan["stop"],
                "target_1": plan["t1"],
                "target_2": plan["t2"],
                "risk_reward": plan["rr"],
                "quant_score": q,
                "evidence_score": evidence,
                "market_regime": regime,
                "reasoning": base_reason[:4000],
                "strategy_version": STRATEGY_VERSION,
                "_rank_score": rank_score,
            })
        ranked.sort(key=lambda x: x["_rank_score"], reverse=True)
        rows = ranked[:20]
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row.pop("_rank_score", None)
        replace_opportunities(scan_id, horizon, rows)
        saved[horizon] = rows
    return saved

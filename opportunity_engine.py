import logging
from datetime import timedelta

from config import STRATEGY_VERSION
from calibration import calibration_assessment
from db import fetch_resolved_predictions, insert_prediction_ledger, replace_opportunities
from production_validation import validate_live_strategy
from utils import iso, now_utc

log = logging.getLogger(__name__)


def _entry_zone(plan):
    risk = abs(plan["entry"] - plan["stop"])
    pad = risk * 0.10
    return plan["entry"] - pad, plan["entry"] + pad


def _bounded_multiplier(value, default=0.0):
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def build_opportunities(scan_id, candidates, ai_signals, regime, risk_plan_fn):
    """Persist top-20 24h and 7d rankings from the current scan.

    Direction/rank comes from deterministic multi-timeframe quant evidence.
    BUY/SELL eligibility is fail-closed. Market-data quality is restrictive:
    stale, missing or contradictory independent exchange evidence can only lower
    displayed evidence/rank and forces WAIT when consensus is not reliable.
    """
    ai_map = {}
    for s in ai_signals or []:
        symbol = str(s.get("symbol", "")).upper()
        horizon = str(s.get("horizon", ""))
        if symbol and horizon in {"24h", "7d"}:
            ai_map[(symbol, horizon)] = s

    resolved_predictions = fetch_resolved_predictions()
    saved = {}
    ledger_rows = []
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
            consensus = c.get("market_consensus", {})
            consensus_reliable = consensus.get("reliable") is True
            data_multiplier = _bounded_multiplier(
                consensus.get("confidence_multiplier"),
                1.0 if consensus_reliable else 0.0,
            )
            if reviewed_direction != direction or action != "TRADE" or not validation.approved or not consensus_reliable:
                action = "WAIT"

            raw_evidence = float(reviewed.get("evidence_score") or min(99.0, abs(q) / 5.5 * 100.0))
            evidence = raw_evidence * data_multiplier
            calibration = calibration_assessment(evidence, horizon, resolved_predictions, regime)
            if action == "TRADE" and not calibration["allows_live_action"]:
                action = "WAIT"

            liquidity_bonus = min(15.0, max(0.0, c.get("activity_score", 0.0)))
            spread_penalty = min(20.0, float(c.get("spread_bps") or 0.0) * 0.35)
            raw_rank_score = max(0.0, abs(q) * 20.0 + liquidity_bonus - spread_penalty)
            rank_score = raw_rank_score * data_multiplier

            base_reason = str(reviewed.get("reasoning") or f"Quant rank from multi-timeframe {horizon} evidence; not AI-approved for trade.")
            if not validation.approved:
                base_reason = f"{base_reason} [{validation.status}: {validation.reason}]"
            elif not calibration["allows_live_action"]:
                base_reason = f"{base_reason} [CALIBRATION_PENDING_OR_WEAK: live action blocked]"
            if not consensus_reliable:
                provenance = consensus.get("provenance") or {}
                accepted = provenance.get("accepted_exchange_names") or []
                base_reason = (
                    f"{base_reason} [MARKET_DATA_RESTRICTED: {consensus.get('reason', 'missing')}; "
                    f"independent_sources={consensus.get('source_count', 0)}; accepted={accepted}; "
                    f"confidence_multiplier={data_multiplier:.3f}; live action blocked]"
                )

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
                "strategy_identity": validation.identity,
                "calibration": calibration,
                "_rank_score": rank_score,
            })
        ranked.sort(key=lambda x: x["_rank_score"], reverse=True)
        rows = ranked[:20]
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row.pop("_rank_score", None)
        replace_opportunities(scan_id, horizon, rows)
        due_at = now_utc() + (timedelta(hours=24) if horizon == "24h" else timedelta(days=7))
        for row in rows:
            ledger_rows.append({
                "scan_id": scan_id,"symbol": row["symbol"],"horizon": horizon,
                "direction": row["direction"],"entry_price": row["entry_price"],
                "score": row["evidence_score"],"market_regime": regime,
                "strategy_identity": row["strategy_identity"],
                "action_at_forecast": row["action"],"due_at": iso(due_at),
                "calibration": row["calibration"],
            })
        saved[horizon] = rows
    insert_prediction_ledger(ledger_rows)
    return saved
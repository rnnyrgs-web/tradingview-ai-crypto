import logging
from datetime import timedelta

from config import STRATEGY_VERSION
from calibration import calibration_assessment
from db import fetch_resolved_predictions, insert_prediction_ledger, replace_opportunities
from operational_monitor import health_snapshot
from production_risk_gate import assess_execution_risk, assess_global_market_risk
from production_validation import validate_live_strategy
from utils import iso, now_utc

log = logging.getLogger(__name__)


PREFLIGHT_CONTEXT_SCHEMA_VERSION = 1


def _entry_zone(plan):
    risk = abs(plan["entry"] - plan["stop"])
    pad = risk * 0.10
    return plan["entry"] - pad, plan["entry"] + pad


def _bounded_multiplier(value, default=0.0):
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _preforecast_market_context(candidate, captured_at):
    """Freeze only market evidence that already existed before forecast creation.

    Historical rows are intentionally untouched. This snapshot is embedded only
    in newly-created prediction-ledger calibration JSON, avoiding any claim that
    the same fields existed for older forecasts. Quote timestamps are retained so
    later research can verify chronology instead of trusting a derived flag alone.
    """
    consensus = candidate.get("market_consensus") if isinstance(candidate, dict) else None
    if not isinstance(consensus, dict):
        return {
            "schema_version": PREFLIGHT_CONTEXT_SCHEMA_VERSION,
            "captured_at": captured_at,
            "market_consensus": {"recorded": False},
        }

    observations = []
    for quote in consensus.get("quotes") or []:
        if not isinstance(quote, dict):
            continue
        exchange = str(quote.get("exchange") or "").strip().lower()
        try:
            observed_ms = int(quote.get("observed_ms") or 0)
        except (TypeError, ValueError):
            observed_ms = 0
        if exchange and observed_ms > 0:
            observations.append({"exchange": exchange, "observed_ms": observed_ms})

    provenance = consensus.get("provenance") if isinstance(consensus.get("provenance"), dict) else {}
    accepted_names = provenance.get("accepted_exchange_names") or []
    accepted_names = sorted({str(name).strip().lower() for name in accepted_names if str(name).strip()})
    source_count = int(consensus.get("source_count") or 0)
    required_source_count = int(consensus.get("required_source_count") or 0)

    return {
        "schema_version": PREFLIGHT_CONTEXT_SCHEMA_VERSION,
        "captured_at": captured_at,
        "market_consensus": {
            "recorded": True,
            "reliable_at_forecast": consensus.get("reliable") is True,
            "reason": str(consensus.get("reason") or "missing"),
            "independent_source_count": source_count,
            "required_source_count": required_source_count,
            "price_range_bps": consensus.get("price_range_bps"),
            "max_quote_age_seconds": consensus.get("max_quote_age_seconds"),
            "confidence_multiplier": _bounded_multiplier(consensus.get("confidence_multiplier")),
            "accepted_exchange_names": accepted_names,
            "accepted_observations": sorted(observations, key=lambda row: (row["exchange"], row["observed_ms"])),
        },
    }


def build_opportunities(scan_id, candidates, ai_signals, regime, risk_plan_fn):
    ai_map = {}
    for s in ai_signals or []:
        symbol = str(s.get("symbol", "")).upper()
        horizon = str(s.get("horizon", ""))
        if symbol and horizon in {"24h", "7d"}:
            ai_map[(symbol, horizon)] = s

    resolved_predictions = fetch_resolved_predictions()
    global_risk = assess_global_market_risk(candidates, health_snapshot())
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
                log.warning("Opportunity rejected because risk plan failed: symbol=%s horizon=%s error=%s", c.get("symbol"), horizon, type(exc).__name__)
                continue
            entry_low, entry_high = _entry_zone(plan)
            reviewed = ai_map.get((c["symbol"], horizon), {})
            reviewed_direction = str(reviewed.get("direction", "")).upper()
            action = str(reviewed.get("action", "WAIT")).upper()
            strategy_family = str(reviewed.get("strategy_family", ""))
            validation = validate_live_strategy(c["symbol"], horizon, strategy_family, resolved_predictions)
            consensus = c.get("market_consensus", {})
            consensus_reliable = consensus.get("reliable") is True
            data_multiplier = _bounded_multiplier(consensus.get("confidence_multiplier"), 1.0 if consensus_reliable else 0.0)
            execution_risk = assess_execution_risk(c, direction)
            if (
                reviewed_direction != direction
                or action != "TRADE"
                or not validation.approved
                or not consensus_reliable
                or global_risk.blocked
                or execution_risk.blocked
            ):
                action = "WAIT"

            raw_evidence = float(reviewed.get("evidence_score") or min(99.0, abs(q) / 5.5 * 100.0))
            evidence = raw_evidence * data_multiplier
            calibration = calibration_assessment(evidence, horizon, resolved_predictions, regime)
            if action == "TRADE" and not calibration["allows_live_action"]:
                action = "WAIT"

            liquidity_bonus = min(15.0, max(0.0, c.get("activity_score", 0.0)))
            spread_penalty = min(20.0, float(c.get("spread_bps") or 0.0) * 0.35)
            rank_score = max(0.0, abs(q) * 20.0 + liquidity_bonus - spread_penalty) * data_multiplier
            base_reason = str(reviewed.get("reasoning") or f"Quant rank from multi-timeframe {horizon} evidence; not AI-approved for trade.")
            if not validation.approved:
                base_reason = f"{base_reason} [{validation.status}: {validation.reason}]"
            elif not calibration["allows_live_action"]:
                base_reason = f"{base_reason} [CALIBRATION_PENDING_OR_WEAK: live action blocked]"
            if global_risk.blocked:
                base_reason = f"{base_reason} [GLOBAL_RISK_WAIT: {','.join(global_risk.reasons)}]"
            if execution_risk.blocked:
                base_reason = f"{base_reason} [EXECUTION_RISK_WAIT: {','.join(execution_risk.reasons)}]"
            if not consensus_reliable:
                provenance = consensus.get("provenance") or {}
                accepted = provenance.get("accepted_exchange_names") or []
                base_reason = (
                    f"{base_reason} [MARKET_CONSENSUS_UNRELIABLE] [MARKET_DATA_RESTRICTED: {consensus.get('reason', 'missing')}; "
                    f"independent_sources={consensus.get('source_count', 0)}; accepted={accepted}; confidence_multiplier={data_multiplier:.3f}; live action blocked]"
                )

            ranked.append({
                "scan_id": scan_id,"horizon": horizon,"symbol": c["symbol"],"direction": direction,"action": action,
                "entry_price": plan["entry"],"entry_low": entry_low,"entry_high": entry_high,"stop_loss": plan["stop"],
                "target_1": plan["t1"],"target_2": plan["t2"],"risk_reward": plan["rr"],"quant_score": q,
                "evidence_score": evidence,"market_regime": regime,"reasoning": base_reason[:4000],"strategy_version": STRATEGY_VERSION,
                "strategy_identity": validation.identity,"calibration": calibration,"_rank_score": rank_score,
                "_preforecast_market_context": _preforecast_market_context(c, iso(now_utc())),
            })
        ranked.sort(key=lambda x: x["_rank_score"], reverse=True)
        rows = ranked[:20]
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row.pop("_rank_score", None)
        replace_opportunities(scan_id, horizon, rows)
        due_at = now_utc() + (timedelta(hours=24) if horizon == "24h" else timedelta(days=7))
        for row in rows:
            ledger_calibration = dict(row["calibration"])
            ledger_calibration["preforecast_market_context"] = row.pop("_preforecast_market_context")
            ledger_rows.append({
                "scan_id": scan_id,"symbol": row["symbol"],"horizon": horizon,"direction": row["direction"],"entry_price": row["entry_price"],
                "score": row["evidence_score"],"market_regime": regime,"strategy_identity": row["strategy_identity"],
                "action_at_forecast": row["action"],"due_at": iso(due_at),"calibration": ledger_calibration,
            })
        saved[horizon] = rows
    insert_prediction_ledger(ledger_rows)
    return saved

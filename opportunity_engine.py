import logging
from datetime import timedelta

from config import HORIZONS, OPPORTUNITY_HORIZONS, STRATEGY_VERSION
from calibration import calibration_assessment
from db import fetch_resolved_predictions, insert_prediction_ledger, replace_opportunities
from operational_monitor import health_snapshot
from production_risk_gate import assess_execution_risk, assess_global_market_risk
from production_validation import validate_live_strategy
from utils import iso, now_utc

log = logging.getLogger(__name__)

PREFLIGHT_CONTEXT_SCHEMA_VERSION = 1
ACTION_DIAGNOSTICS_SCHEMA_VERSION = 1


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
    consensus = candidate.get("market_consensus") if isinstance(candidate, dict) else None
    if not isinstance(consensus, dict):
        return {"schema_version": PREFLIGHT_CONTEXT_SCHEMA_VERSION,"captured_at": captured_at,"market_consensus": {"recorded": False}}
    observations=[]
    for quote in consensus.get("quotes") or []:
        if not isinstance(quote,dict): continue
        exchange=str(quote.get("exchange") or "").strip().lower()
        try: observed_ms=int(quote.get("observed_ms") or 0)
        except (TypeError,ValueError): observed_ms=0
        if exchange and observed_ms>0: observations.append({"exchange":exchange,"observed_ms":observed_ms})
    provenance=consensus.get("provenance") if isinstance(consensus.get("provenance"),dict) else {}
    accepted_names=sorted({str(x).strip().lower() for x in (provenance.get("accepted_exchange_names") or []) if str(x).strip()})
    return {"schema_version":PREFLIGHT_CONTEXT_SCHEMA_VERSION,"captured_at":captured_at,"market_consensus":{
        "recorded":True,"reliable_at_forecast":consensus.get("reliable") is True,"reason":str(consensus.get("reason") or "missing"),
        "independent_source_count":int(consensus.get("source_count") or 0),"required_source_count":int(consensus.get("required_source_count") or 0),
        "price_range_bps":consensus.get("price_range_bps"),"max_quote_age_seconds":consensus.get("max_quote_age_seconds"),
        "confidence_multiplier":_bounded_multiplier(consensus.get("confidence_multiplier")),"accepted_exchange_names":accepted_names,
        "accepted_observations":sorted(observations,key=lambda r:(r["exchange"],r["observed_ms"]))}}


def _attach_universe_snapshot(ledger_rows, scan_id, universe_snapshot):
    """Attach one bounded pre-outcome universe snapshot per scan, never one copy per forecast."""
    if not ledger_rows or not isinstance(universe_snapshot, dict):
        return False
    symbols=universe_snapshot.get("symbols")
    if (
        universe_snapshot.get("recorded") is not True
        or str(universe_snapshot.get("scan_id") or "") != str(scan_id)
        or not isinstance(symbols, list)
        or not symbols
    ):
        return False
    snapshot=dict(universe_snapshot)
    snapshot["symbols"]=list(symbols)
    calibration=dict(ledger_rows[0].get("calibration") or {})
    calibration["preforecast_universe_snapshot"]=snapshot
    ledger_rows[0]["calibration"]=calibration
    return True


def _diagnostic(category, code, detail=None):
    item={"category":category,"code":code}
    if detail:
        item["detail"]=str(detail)[:240]
    return item


def _market_consensus_category(reason):
    reason=str(reason or "missing")
    if reason in {"exchange_price_disagreement"}:
        return "market_liquidity"
    return "technical_data_infrastructure"


def _global_risk_category(reason):
    if reason in {"broad_market_volatility_shock","broad_liquidity_stress"}:
        return "market_liquidity"
    return "technical_data_infrastructure"


def _execution_risk_category(reason):
    if reason in {"spread_too_wide","insufficient_visible_depth","visible_slippage_too_high","cross_exchange_book_disagreement"}:
        return "market_liquidity"
    return "technical_data_infrastructure"


def _action_diagnostics(reviewed_present, reviewed_direction, direction, reviewed_action, validation, consensus, global_risk, execution_risk, calibration, pre_calibration_action):
    reasons=[]
    if not reviewed_present:
        reasons.append(_diagnostic("strategy_evidence","upstream_review_missing","candidate was not returned by the bounded AI review"))
    elif reviewed_direction != direction:
        reasons.append(_diagnostic("strategy_evidence","review_direction_mismatch",f"reviewed={reviewed_direction or 'missing'} quant={direction}"))
    if reviewed_present and reviewed_action != "TRADE":
        reasons.append(_diagnostic("strategy_evidence","upstream_review_wait",f"reviewed_action={reviewed_action or 'WAIT'}"))
    if not validation.approved:
        reasons.append(_diagnostic("strategy_evidence","strategy_validation_blocked",f"{validation.status}: {validation.reason}"))
    if consensus.get("reliable") is not True:
        consensus_reason=str(consensus.get("reason") or "missing")
        reasons.append(_diagnostic(_market_consensus_category(consensus_reason),"market_consensus_unreliable",consensus_reason))
    for reason in global_risk.reasons:
        reasons.append(_diagnostic(_global_risk_category(reason),f"global_risk_{reason}"))
    for reason in execution_risk.reasons:
        reasons.append(_diagnostic(_execution_risk_category(reason),f"execution_risk_{reason}"))
    if pre_calibration_action == "TRADE" and not calibration["allows_live_action"]:
        reasons.append(_diagnostic("strategy_evidence","calibration_pending_or_weak"))
    return {
        "schema_version":ACTION_DIAGNOSTICS_SCHEMA_VERSION,
        "blocked":bool(reasons),
        "primary_category":reasons[0]["category"] if reasons else None,
        "primary_reason":reasons[0]["code"] if reasons else None,
        "reasons":reasons,
        "thresholds_unchanged":True,
        "trade_authority_added":False,
    }


def build_opportunities(scan_id,candidates,ai_signals,regime,risk_plan_fn,universe_snapshot=None):
    ai_map={}
    for s in ai_signals or []:
        symbol=str(s.get("symbol","")).upper(); horizon=str(s.get("horizon",""))
        if symbol and horizon in OPPORTUNITY_HORIZONS: ai_map[(symbol,horizon)]=s
    resolved_predictions=fetch_resolved_predictions()
    global_risk=assess_global_market_risk(candidates,health_snapshot())
    saved={}; ledger_rows=[]
    for horizon in OPPORTUNITY_HORIZONS:
        ranked=[]
        for c in candidates:
            hv=c.get("horizons",{}).get(horizon)
            if not hv: continue
            q=float(hv.get("score") or 0.0); direction="LONG" if q>=0 else "SHORT"
            try: plan=risk_plan_fn(hv["features"],direction,horizon)
            except Exception as exc:
                log.warning("Opportunity rejected because risk plan failed: symbol=%s horizon=%s error=%s",c.get("symbol"),horizon,type(exc).__name__); continue
            entry_low,entry_high=_entry_zone(plan)
            reviewed=ai_map.get((c["symbol"],horizon),{}); reviewed_present=bool(reviewed); reviewed_direction=str(reviewed.get("direction","")).upper(); reviewed_action=str(reviewed.get("action","WAIT")).upper(); action=reviewed_action
            strategy_family=str(reviewed.get("strategy_family","")); validation=validate_live_strategy(c["symbol"],horizon,strategy_family,resolved_predictions)
            consensus=c.get("market_consensus",{}); consensus_reliable=consensus.get("reliable") is True
            data_multiplier=_bounded_multiplier(consensus.get("confidence_multiplier"),1.0 if consensus_reliable else 0.0)
            execution_risk=assess_execution_risk(c,direction)
            if reviewed_direction!=direction or action!="TRADE" or not validation.approved or not consensus_reliable or global_risk.blocked or execution_risk.blocked: action="WAIT"
            raw_evidence=float(reviewed.get("evidence_score") or min(99.0,abs(q)/5.5*100.0)); evidence=raw_evidence*data_multiplier
            calibration=calibration_assessment(evidence,horizon,resolved_predictions,regime)
            pre_calibration_action=action
            if action=="TRADE" and not calibration["allows_live_action"]: action="WAIT"
            action_diagnostics=_action_diagnostics(reviewed_present,reviewed_direction,direction,reviewed_action,validation,consensus,global_risk,execution_risk,calibration,pre_calibration_action)
            calibration=dict(calibration); calibration["action_diagnostics"]=action_diagnostics
            liquidity_bonus=min(15.0,max(0.0,c.get("activity_score",0.0))); spread_penalty=min(20.0,float(c.get("spread_bps") or 0.0)*0.35)
            rank_score=max(0.0,abs(q)*20.0+liquidity_bonus-spread_penalty)*data_multiplier
            base_reason=str(reviewed.get("reasoning") or f"Quant rank from multi-timeframe {horizon} evidence; not AI-approved for trade.")
            if not validation.approved: base_reason=f"{base_reason} [{validation.status}: {validation.reason}]"
            elif not calibration["allows_live_action"]: base_reason=f"{base_reason} [CALIBRATION_PENDING_OR_WEAK: live action blocked]"
            if global_risk.blocked: base_reason=f"{base_reason} [GLOBAL_RISK_WAIT: {','.join(global_risk.reasons)}]"
            if execution_risk.blocked: base_reason=f"{base_reason} [EXECUTION_RISK_WAIT: {','.join(execution_risk.reasons)}]"
            if not consensus_reliable:
                provenance=consensus.get("provenance") or {}; accepted=provenance.get("accepted_exchange_names") or []
                base_reason=f"{base_reason} [MARKET_CONSENSUS_UNRELIABLE] [MARKET_DATA_RESTRICTED: {consensus.get('reason','missing')}; independent_sources={consensus.get('source_count',0)}; accepted={accepted}; confidence_multiplier={data_multiplier:.3f}; live action blocked]"
            ranked.append({"scan_id":scan_id,"horizon":horizon,"symbol":c["symbol"],"direction":direction,"action":action,"entry_price":plan["entry"],"entry_low":entry_low,"entry_high":entry_high,"stop_loss":plan["stop"],"target_1":plan["t1"],"target_2":plan["t2"],"risk_reward":plan["rr"],"quant_score":q,"evidence_score":evidence,"market_regime":regime,"reasoning":base_reason[:4000],"strategy_version":STRATEGY_VERSION,"strategy_identity":validation.identity,"calibration":calibration,"_rank_score":rank_score,"_preforecast_market_context":_preforecast_market_context(c,iso(now_utc()))})
        ranked.sort(key=lambda x:x["_rank_score"],reverse=True); rows=ranked[:20]
        for i,row in enumerate(rows,1): row["rank"]=i; row.pop("_rank_score",None)
        replace_opportunities(scan_id,horizon,rows)
        due_at=now_utc()+timedelta(hours=int(HORIZONS[horizon]["hold_hours"]))
        for row in rows:
            ledger_calibration=dict(row["calibration"]); ledger_calibration["preforecast_market_context"]=row.pop("_preforecast_market_context")
            ledger_rows.append({"scan_id":scan_id,"symbol":row["symbol"],"horizon":horizon,"direction":row["direction"],"entry_price":row["entry_price"],"score":row["evidence_score"],"market_regime":regime,"strategy_identity":row["strategy_identity"],"action_at_forecast":row["action"],"due_at":iso(due_at),"calibration":ledger_calibration})
        saved[horizon]=rows
    _attach_universe_snapshot(ledger_rows,scan_id,universe_snapshot)
    insert_prediction_ledger(ledger_rows)
    return saved
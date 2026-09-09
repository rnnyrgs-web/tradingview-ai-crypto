import json, re, uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from config import *
from utils import clamp
from market_data import build_universe, get_candles, get_derivatives, get_order_book_intelligence
from features import timeframe_features
from safety import validate_candles, validate_risk, SafetyError
from news_engine import latest_news, for_base
from db import insert_signal
from opportunity_engine import build_opportunities
from production_validation import validate_live_strategy
from production_risk_gate import assess_execution_risk, assess_global_market_risk
from operational_monitor import health_snapshot, record_scan
from scan_failure_diagnostics import safe_failure

client = OpenAI(api_key=OPENAI_API_KEY)
log = logging.getLogger(__name__)

def horizon_score(symbol, horizon):
    cfg=HORIZONS[horizon]
    parts=[]
    for bar in cfg["bars"]:
        candles=get_candles(symbol,bar,140 if bar!="1D" else 100)
        validate_candles(candles,symbol,bar)
        ft=timeframe_features(candles)
        parts.append((bar,ft))
    weights = [0.62,0.38] if len(parts)==2 else [1.0]
    score=sum(ft["score"]*w for (_,ft),w in zip(parts,weights))
    return score, {bar:ft for bar,ft in parts}

def detect_regime(cands):
    if not cands:
        return "UNKNOWN"
    scores=[c["horizons"]["24h"]["score"] for c in cands if "24h" in c["horizons"]]
    if not scores:
        return "UNKNOWN"
    avg=sum(scores)/len(scores)
    pos=sum(1 for s in scores if s>0)/len(scores)
    if avg>1.0 and pos>0.68:
        return "BULL_TREND"
    if avg<-1.0 and pos<0.32:
        return "BEAR_TREND"
    if abs(avg)<0.45:
        return "RANGE_MIXED"
    return "TRANSITIONAL"

def risk_plan(features, direction, horizon):
    ft=next(iter(features.values()))
    entry=ft["last"]
    a=ft["atr"]
    mult={"intraday":1.45,"24h":1.8,"7d":2.25,"30d":2.8}[horizon]
    risk=max(a*mult,entry*0.0035)
    if direction=="LONG":
        stop=entry-risk; t1=entry+risk*1.9; t2=entry+risk*3.0
    else:
        stop=entry+risk; t1=entry-risk*1.9; t2=entry-risk*3.0
    validate_risk(direction,entry,stop,t1,t2)
    return {"entry":entry,"stop":stop,"t1":t1,"t2":t2,"rr":1.9}

def _preflight_opportunity_risk(candidates):
    """Remove only horizons whose current ATR risk geometry is not representable.

    A very volatile low-priced asset can legitimately imply a negative target or
    stop under the fixed ATR geometry. We must not clamp or manufacture a valid
    looking plan. Instead that symbol/horizon fails closed to WAIT by being
    omitted from the opportunity builder for this scan. Other horizons for the
    same asset remain eligible.
    """
    eligible=[]
    rejected=[]
    for candidate in candidates:
        horizons=dict(candidate.get("horizons") or {})
        for horizon in ("24h","7d"):
            hv=horizons.get(horizon)
            if not isinstance(hv,dict):
                continue
            score=float(hv.get("score") or 0.0)
            direction="LONG" if score>=0 else "SHORT"
            try:
                risk_plan(hv.get("features") or {},direction,horizon)
            except (SafetyError, KeyError, StopIteration, TypeError, ValueError):
                horizons.pop(horizon,None)
                rejected.append({"symbol":candidate.get("symbol"),"horizon":horizon})
        if horizons:
            eligible.append({**candidate,"horizons":horizons})
    if rejected:
        log.info("Opportunity risk preflight safely suppressed %s unrepresentable symbol/horizon plans",len(rejected))
    return eligible,rejected

def compact(c):
    return {
        "symbol":c["symbol"],
        "change_24h_pct":round(c["change_24h_pct"],3),
        "spread_bps":round(c["spread_bps"],3),
        "quote_volume_24h":round(c["quote_volume_24h"],2),
        "market_consensus":c.get("market_consensus", {"reliable":False,"reason":"missing"}),
        "derivatives":c["derivatives"],
        "order_book":c.get("order_book", {"research_only":True,"reliable":False,"reason":"not_sampled"}),
        "horizons":{
            h:{
                "score":round(v["score"],3),
                "features":{
                    bar:{k:round(x,5) for k,x in ft.items() if isinstance(x,(int,float))}
                    for bar,ft in v["features"].items()
                }
            }
            for h,v in c["horizons"].items()
        }
    }

def extract_json(text):
    text=text.strip()
    text=re.sub(r"^```(?:json)?\s*","",text,flags=re.I)
    text=re.sub(r"\s*```$","",text)
    try:
        return json.loads(text)
    except Exception:
        m=re.search(r"\{.*\}",text,flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))

def ai_review(candidates, regime, news):
    payload=[compact(c) for c in candidates]
    headlines=[n["title"] for n in news[:20]]
    prompt=f"""
You are the adversarial review component of a crypto research system.
Do NOT invent missing data. Evidence score is NOT probability.

Market regime: {regime}
Candidates: {json.dumps(payload,separators=(",",":"),ensure_ascii=False)}
Headlines: {json.dumps(headlines,ensure_ascii=False)}

For each candidate/horizon, challenge the setup. Reject contradictory, overextended,
illiquid, news-risky or weak setups. Do not force trades. strategy_family is only
an advisory label and can never itself authorize a live trade.

Return ONLY JSON:
{{
 "summary":"short",
 "signals":[
   {{
     "symbol":"BTC-USDT",
     "horizon":"intraday|24h|7d|30d",
     "direction":"LONG|SHORT",
     "strategy_family":"trend|breakout|momentum|mean_reversion|volatility_expansion|relative_strength_btc",
     "action":"TRADE|WAIT",
     "evidence_score":0,
     "reasoning":"short",
     "invalidation":"short"
   }}
 ]
}}
Maximum 6 signals total.
"""
    r=client.responses.create(model=OPENAI_MODEL,input=prompt)
    return extract_json(r.output_text)

def run_scan():
    scan_id=str(uuid.uuid4())
    universe=build_universe()
    pre=universe[:DEEP_SCAN_SIZE]
    deep=[]
    errors=[]

    for item in pre:
        try:
            hs={}
            for h in ("intraday","24h","7d","30d"):
                score, feats=horizon_score(item["symbol"],h)
                hs[h]={"score":score,"features":feats}
            item={**item,"horizons":hs,"derivatives":get_derivatives(item["base"])}
            item["rank_score"]=max(abs(v["score"]) for v in hs.values())
            deep.append(item)
        except Exception as e:
            errors.append({"symbol":item["symbol"],"error":str(e)})

    deep.sort(key=lambda x:x["rank_score"],reverse=True)
    finalists=deep[:AI_CANDIDATES]
    with ThreadPoolExecutor(max_workers=min(6, len(finalists) or 1)) as pool:
        pending = {pool.submit(get_order_book_intelligence, item["base"]): item for item in finalists}
        for future in as_completed(pending):
            item = pending[future]
            try:
                item["order_book"] = future.result()
            except Exception as exc:
                log.info("Order-book intelligence unavailable for %s: %s", item["symbol"], type(exc).__name__)
                item["order_book"] = {"research_only":True,"reliable":False,"reason":"collection_error"}
    regime=detect_regime(finalists)
    news=latest_news()
    global_risk=assess_global_market_risk(finalists, health_snapshot())

    try:
        review=ai_review(finalists,regime,news)
        signals=review.get("signals") or []
        ai_error=None
    except Exception as e:
        signals=[]
        ai_error=str(e)

    opportunity_error=None
    opportunity_failure=None
    opportunities={"24h":[],"7d":[]}
    opportunity_candidates,risk_preflight_rejections=_preflight_opportunity_risk(deep)
    try:
        opportunities=build_opportunities(scan_id,opportunity_candidates,signals,regime,risk_plan)
    except Exception as e:
        opportunity_error=type(e).__name__
        opportunity_failure=safe_failure("opportunity_persistence", e)
        log.exception("Opportunity persistence failed fingerprint=%s", opportunity_failure["fingerprint"])

    saved=[]
    for s in signals[:MAX_SAVED_SIGNALS]:
        symbol=str(s.get("symbol","")).upper()
        horizon=str(s.get("horizon",""))
        direction=str(s.get("direction","")).upper()
        action=str(s.get("action","WAIT")).upper()
        evidence=float(s.get("evidence_score") or 0)
        strategy_family=str(s.get("strategy_family","")).strip().lower()

        c=next((x for x in finalists if x["symbol"]==symbol),None)
        if not c or horizon not in HORIZONS or direction not in {"LONG","SHORT"}:
            continue

        try:
            plan=risk_plan(c["horizons"][horizon]["features"],direction,horizon)
        except (SafetyError, KeyError, StopIteration, TypeError, ValueError):
            log.info("AI signal safely skipped because risk geometry is unrepresentable: symbol=%s horizon=%s",symbol,horizon)
            continue
        validation=validate_live_strategy(symbol,horizon,strategy_family)
        consensus=c.get("market_consensus", {})
        execution_risk=assess_execution_risk(c,direction)
        if (
            evidence < MIN_EVIDENCE_SCORE
            or plan["rr"] < MIN_RR
            or not validation.approved
            or not consensus.get("reliable")
            or global_risk.blocked
            or execution_risk.blocked
        ):
            action="WAIT"

        reasoning=str(s.get("reasoning","")).strip()
        if not validation.approved:
            reasoning=(f"{reasoning} [{validation.status}: {validation.reason}]" if reasoning else f"{validation.status}: {validation.reason}")
        if not consensus.get("reliable"):
            reasoning=(f"{reasoning} [MARKET_CONSENSUS_UNRELIABLE: {consensus.get('reason', 'missing')}]" if reasoning else "MARKET_CONSENSUS_UNRELIABLE")
        if global_risk.blocked:
            reasoning=(f"{reasoning} [GLOBAL_RISK_WAIT: {','.join(global_risk.reasons)}]" if reasoning else f"GLOBAL_RISK_WAIT: {','.join(global_risk.reasons)}")
        if execution_risk.blocked:
            reasoning=(f"{reasoning} [EXECUTION_RISK_WAIT: {','.join(execution_risk.reasons)}]" if reasoning else f"EXECUTION_RISK_WAIT: {','.join(execution_risk.reasons)}")

        row={
            "scan_id":scan_id,"symbol":symbol,"timeframe":horizon,"direction":direction,"action":action,
            "entry_price":plan["entry"],"stop_loss":plan["stop"],"target_1":plan["t1"],"target_2":plan["t2"],
            "risk_reward":plan["rr"],"evidence_score":evidence,"market_regime":regime,
            "reasoning":reasoning[:4000],"status":"OPEN","model_name":OPENAI_MODEL,
            "strategy_version":STRATEGY_VERSION,"raw_analysis":{
                "candidate":compact(c),"ai_signal":s,
                "research_validation":{
                    "approved":validation.approved,
                    "status":validation.status,
                    "reason":validation.reason,
                    "strategy_family":strategy_family,
                    "strategy_identity":validation.identity,
                },
                "execution_risk":{
                    "blocked":execution_risk.blocked,"reasons":list(execution_risk.reasons),"metrics":execution_risk.metrics,
                },
                "global_risk":{
                    "blocked":global_risk.blocked,"reasons":list(global_risk.reasons),"metrics":global_risk.metrics,
                },
                "headline_context":[n["title"] for n in for_base(c["base"],news)[:5]]
            }
        }
        insert_signal(row)
        saved.append(row)

    result = {
        "ok":not ai_error and not opportunity_error and bool(deep),"version":STRATEGY_VERSION,"scan_id":scan_id,
        "universe_count":len(universe),"deep_scanned":len(deep),"market_regime":regime,
        "signals_saved":len(saved),"signals":saved,"scan_error_count":len(errors),
        "scan_errors":errors[:20],"ai_error":ai_error,
        "opportunities_saved":{"24h":len(opportunities.get("24h",[])),"7d":len(opportunities.get("7d",[]))},
        "opportunity_error":opportunity_error,"opportunity_failure":opportunity_failure,
        "risk_preflight_rejection_count":len(risk_preflight_rejections),
        "global_risk_wait":global_risk.blocked,
        "global_risk_reasons":list(global_risk.reasons),
    }
    record_scan(result)
    if errors:
        log.warning("Scan completed with %s symbol errors", len(errors))
    return result

import json, re, uuid
from openai import OpenAI

from config import *
from utils import clamp
from market_data import build_universe, get_candles, get_derivatives
from features import timeframe_features
from safety import validate_candles, validate_risk, SafetyError
from news_engine import latest_news, for_base
from db import insert_signal

client = OpenAI(api_key=OPENAI_API_KEY)

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
    # Use shortest bar ATR inside horizon for entry risk.
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

def compact(c):
    return {
        "symbol":c["symbol"],
        "change_24h_pct":round(c["change_24h_pct"],3),
        "spread_bps":round(c["spread_bps"],3),
        "quote_volume_24h":round(c["quote_volume_24h"],2),
        "derivatives":c["derivatives"],
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
illiquid, news-risky or weak setups. Do not force trades.

Return ONLY JSON:
{{
 "summary":"short",
 "signals":[
   {{
     "symbol":"BTC-USDT",
     "horizon":"intraday|24h|7d|30d",
     "direction":"LONG|SHORT",
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
    # Cheap prefilter: strongest movers + liquidity/activity.
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
            # rank by strongest absolute horizon evidence
            item["rank_score"]=max(abs(v["score"]) for v in hs.values())
            deep.append(item)
        except Exception as e:
            errors.append({"symbol":item["symbol"],"error":str(e)})

    deep.sort(key=lambda x:x["rank_score"],reverse=True)
    finalists=deep[:AI_CANDIDATES]
    regime=detect_regime(finalists)
    news=latest_news()

    try:
        review=ai_review(finalists,regime,news)
        signals=review.get("signals") or []
        ai_error=None
    except Exception as e:
        signals=[]
        ai_error=str(e)

    saved=[]
    for s in signals[:MAX_SAVED_SIGNALS]:
        symbol=str(s.get("symbol","")).upper()
        horizon=str(s.get("horizon",""))
        direction=str(s.get("direction","")).upper()
        action=str(s.get("action","WAIT")).upper()
        evidence=float(s.get("evidence_score") or 0)

        c=next((x for x in finalists if x["symbol"]==symbol),None)
        if not c or horizon not in HORIZONS or direction not in {"LONG","SHORT"}:
            continue

        plan=risk_plan(c["horizons"][horizon]["features"],direction,horizon)
        if evidence < MIN_EVIDENCE_SCORE or plan["rr"] < MIN_RR:
            action="WAIT"

        row={
            "scan_id":scan_id,
            "symbol":symbol,
            "timeframe":horizon,
            "direction":direction,
            "action":action,
            "entry_price":plan["entry"],
            "stop_loss":plan["stop"],
            "target_1":plan["t1"],
            "target_2":plan["t2"],
            "risk_reward":plan["rr"],
            "evidence_score":evidence,
            "market_regime":regime,
            "reasoning":str(s.get("reasoning",""))[:4000],
            "status":"OPEN",
            "model_name":OPENAI_MODEL,
            "strategy_version":STRATEGY_VERSION,
            "raw_analysis":{
                "candidate":compact(c),
                "ai_signal":s,
                "headline_context":[n["title"] for n in for_base(c["base"],news)[:5]]
            }
        }
        insert_signal(row)
        saved.append(row)

    return {
        "ok":True,"version":STRATEGY_VERSION,"scan_id":scan_id,
        "universe_count":len(universe),"deep_scanned":len(deep),
        "market_regime":regime,"signals_saved":len(saved),
        "signals":saved,"scan_errors":errors[:20],"ai_error":ai_error
    }

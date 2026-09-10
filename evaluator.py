from datetime import timedelta, datetime, timezone

from utils import f, parse_dt, now_utc, iso
from market_data import get_candles
from db import fetch_due_predictions, fetch_recent, patch_prediction, patch_signal

HORIZON_MAP = {
    "intraday": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "72h": timedelta(hours=72),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "15m": timedelta(hours=24),  # compatibility with old rows
}
PREDICTION_OUTCOME_BAR = "1H"
MAX_PREDICTION_OUTCOME_LAG_MS = int(timedelta(hours=2).total_seconds() * 1000)


def directional_return(entry,future,direction):
    raw=(future/entry-1.0)*100.0
    return raw if direction=="LONG" else -raw


def nearest_close(candles,target_ms):
    for c in candles:
        if c["ts"]>=target_ms:
            return c["close"]
    return candles[-1]["close"] if candles else None


def close_at_or_after(candles,target_ms,max_lag_ms=None):
    for candle in candles:
        ts = candle["ts"]
        if ts < target_ms:
            continue
        if max_lag_ms is not None and ts - target_ms > max_lag_ms:
            return None
        return candle["close"]
    return None


def run_evaluation():
    signals=fetch_recent(hours=24*35,limit=1000)
    updated=0
    errors=[]

    for sig in signals:
        try:
            created=parse_dt(sig["created_at"])
            age=now_utc()-created
            entry=f(sig.get("entry_price"))
            direction=str(sig.get("direction","")).upper()
            if entry<=0 or direction not in {"LONG","SHORT"}:
                continue
            bar="5m" if age<=timedelta(hours=24) else "1H"
            candles=get_candles(sig["symbol"],bar,300)
            if not candles:
                continue
            fields={"evaluated_at":iso(now_utc())}
            checks=[
                (timedelta(minutes=15),"price_15m","return_15m"),
                (timedelta(hours=1),"price_1h","return_1h"),
                (timedelta(hours=4),"price_4h","return_4h"),
                (timedelta(hours=12),"price_12h","return_12h"),
                (timedelta(hours=24),"price_24h","return_24h"),
            ]
            for delta,pcol,rcol in checks:
                if age>=delta and sig.get(pcol) is None:
                    p=nearest_close(candles,int((created+delta).timestamp()*1000))
                    if p is not None:
                        fields[pcol]=p
                        fields[rcol]=directional_return(entry,p,direction)
            tf=str(sig.get("timeframe") or "15m")
            hold=HORIZON_MAP.get(tf,timedelta(hours=24))
            if age>=hold and sig.get("status")!="RESOLVED":
                fields["resolved_at"]=iso(now_utc())
                fields["status"]="RESOLVED"
                if str(sig.get("action","WAIT")).upper()!="TRADE":
                    fields["outcome"]="NO_TRADE"
                else:
                    target=f(sig.get("target_1")); stop=f(sig.get("stop_loss"))
                    path=[c for c in candles if c["ts"]>=int(created.timestamp()*1000)]
                    hit_t=hit_s=None
                    for c in path:
                        if direction=="LONG":
                            ht=target>0 and c["high"]>=target; hs=stop>0 and c["low"]<=stop
                        else:
                            ht=target>0 and c["low"]<=target; hs=stop>0 and c["high"]>=stop
                        ts=datetime.fromtimestamp(c["ts"]/1000,tz=timezone.utc)
                        if ht and hit_t is None: hit_t=ts
                        if hs and hit_s is None: hit_s=ts
                    if hit_t and hit_s:
                        fields["outcome"]="WIN" if hit_t<hit_s else "LOSS" if hit_s<hit_t else "AMBIGUOUS"
                    elif hit_t: fields["outcome"]="WIN"
                    elif hit_s: fields["outcome"]="LOSS"
                    else: fields["outcome"]="EXPIRED"
            patch_signal(sig["id"],fields)
            updated+=1
        except Exception as e:
            errors.append({"id":sig.get("id"),"error":str(e)})

    predictions=fetch_due_predictions()
    predictions_updated=0
    for prediction in predictions:
        try:
            candles=get_candles(prediction["symbol"],PREDICTION_OUTCOME_BAR,300)
            due=parse_dt(prediction["due_at"])
            outcome=close_at_or_after(candles,int(due.timestamp()*1000),max_lag_ms=MAX_PREDICTION_OUTCOME_LAG_MS)
            entry=f(prediction.get("entry_price")); direction=str(prediction.get("direction","")).upper()
            if outcome is None or entry<=0 or direction not in {"LONG","SHORT"}:
                continue
            result=directional_return(entry,outcome,direction)
            patch_prediction(prediction["id"],{"outcome_price":outcome,"directional_return_pct":result,"correct":result>0,"resolved_at":iso(now_utc())})
            predictions_updated+=1
        except Exception as e:
            errors.append({"prediction_id":prediction.get("id"),"error_type":type(e).__name__})

    return {"ok":not errors,"checked":len(signals),"updated":updated,"predictions_checked":len(predictions),"predictions_updated":predictions_updated,"errors":errors[:20]}

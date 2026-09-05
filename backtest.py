from features import timeframe_features
from market_data import get_history
from utils import mean
from config import BACKTEST_COST_BPS

def directional_return(entry,future,direction):
    raw=(future/entry-1.0)*100.0
    return raw if direction=="LONG" else -raw

def run_backtest(symbol, bar="15m", bars=2500, threshold=2.25):
    hist=get_history(symbol,bar,bars)
    if len(hist)<300:
        raise RuntimeError("Not enough historical candles")

    max_hold={"15m":16,"1H":24,"4H":42,"1D":30}.get(bar,16)
    trades=[]
    i=100

    while i < len(hist)-max_hold-2:
        ft=timeframe_features(hist[:i+1])
        if not ft or abs(ft["score"])<threshold or ft["atr"]<=0:
            i+=1
            continue

        direction="LONG" if ft["score"]>0 else "SHORT"
        entry=hist[i+1]["open"]
        risk=max(ft["atr"]*1.55,entry*0.0035)

        if direction=="LONG":
            stop=entry-risk; target=entry+risk*1.9
        else:
            stop=entry+risk; target=entry-risk*1.9

        exit_price=hist[min(i+1+max_hold,len(hist)-1)]["close"]
        reason="TIME"

        for j in range(i+1,min(i+1+max_hold,len(hist))):
            b=hist[j]
            if direction=="LONG":
                hit_stop=b["low"]<=stop
                hit_target=b["high"]>=target
            else:
                hit_stop=b["high"]>=stop
                hit_target=b["low"]<=target

            # Conservative if both occur in same candle.
            if hit_stop:
                exit_price=stop; reason="STOP"; break
            if hit_target:
                exit_price=target; reason="TARGET"; break

        net=directional_return(entry,exit_price,direction)-BACKTEST_COST_BPS/100.0
        trades.append(net)
        i += max_hold

    wins=[x for x in trades if x>0]
    losses=[x for x in trades if x<=0]
    gp=sum(wins); gl=abs(sum(losses))
    return {
        "ok":True,"symbol":symbol,"bar":bar,"candles":len(hist),
        "trades":len(trades),
        "win_rate_pct":round(len(wins)/len(trades)*100,2) if trades else 0,
        "avg_trade_pct":round(mean(trades),4),
        "profit_factor":round(gp/gl,3) if gl>0 else None,
        "sum_net_returns_pct":round(sum(trades),3),
        "cost_bps_round_trip":BACKTEST_COST_BPS,
        "warning":"Research backtest only. Use walk-forward/holdout results before trusting live signals."
    }

def walk_forward(symbol, bar="15m", bars=3000):
    hist=get_history(symbol,bar,bars)
    if len(hist)<1000:
        raise RuntimeError("Need at least 1000 candles for walk-forward")

    # Split chronologically into 60/20/20 and compare several thresholds.
    n=len(hist)
    train=hist[:int(n*0.6)]
    valid=hist[int(n*0.6):int(n*0.8)]
    test=hist[int(n*0.8):]

    def score_segment(seg, threshold):
        if len(seg)<300:
            return {"trades":0,"avg":0.0}
        max_hold={"15m":16,"1H":24,"4H":42,"1D":30}.get(bar,16)
        rs=[]
        i=100
        while i<len(seg)-max_hold-2:
            ft=timeframe_features(seg[:i+1])
            if not ft or abs(ft["score"])<threshold or ft["atr"]<=0:
                i+=1; continue
            direction="LONG" if ft["score"]>0 else "SHORT"
            entry=seg[i+1]["open"]
            risk=max(ft["atr"]*1.55,entry*0.0035)
            target=entry+risk*1.9 if direction=="LONG" else entry-risk*1.9
            stop=entry-risk if direction=="LONG" else entry+risk
            exit_price=seg[min(i+1+max_hold,len(seg)-1)]["close"]
            for j in range(i+1,min(i+1+max_hold,len(seg))):
                b=seg[j]
                hs=b["low"]<=stop if direction=="LONG" else b["high"]>=stop
                ht=b["high"]>=target if direction=="LONG" else b["low"]<=target
                if hs: exit_price=stop; break
                if ht: exit_price=target; break
            rs.append(directional_return(entry,exit_price,direction)-BACKTEST_COST_BPS/100.0)
            i+=max_hold
        return {"trades":len(rs),"avg":mean(rs),"sum":sum(rs)}

    thresholds=[1.75,2.0,2.25,2.5,2.75,3.0]
    train_scores={t:score_segment(train,t) for t in thresholds}
    viable=[t for t,v in train_scores.items() if v["trades"]>=10]
    if not viable:
        return {"ok":True,"symbol":symbol,"bar":bar,"message":"No viable training threshold"}
    best=max(viable,key=lambda t:train_scores[t]["avg"])
    valid_score=score_segment(valid,best)
    test_score=score_segment(test,best)

    return {
        "ok":True,"symbol":symbol,"bar":bar,
        "selected_threshold":best,
        "train":train_scores[best],
        "validation":valid_score,
        "holdout_test":test_score,
        "note":"Threshold selected on training only; holdout remains untouched until final scoring."
    }

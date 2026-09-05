from utils import mean, safe_stdev, clamp, pct_change

def ema(values, period):
    if not values:
        return 0.0
    alpha = 2.0/(period+1.0)
    e = values[0]
    for v in values[1:]:
        e = alpha*v + (1-alpha)*e
    return e

def rsi(values, period=14):
    if len(values) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(len(values)-period, len(values)):
        d = values[i]-values[i-1]
        gains.append(max(d,0.0))
        losses.append(max(-d,0.0))
    ag, al = mean(gains), mean(losses)
    if al == 0:
        return 100.0
    rs = ag/al
    return 100.0 - 100.0/(1.0+rs)

def atr(candles, period=14):
    if len(candles)<2:
        return 0.0
    trs=[]
    for i in range(max(1,len(candles)-period),len(candles)):
        h,l,pc=candles[i]["high"],candles[i]["low"],candles[i-1]["close"]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return mean(trs)

def zscore_last(values, window=30):
    vals=values[-window:]
    if len(vals)<5:
        return 0.0
    sd=safe_stdev(vals)
    return 0.0 if sd==0 else (vals[-1]-mean(vals))/sd

def slope_pct(values, n=12):
    vals=values[-n:]
    if len(vals)<3 or mean(vals)==0:
        return 0.0
    xbar=(len(vals)-1)/2
    ybar=mean(vals)
    num=sum((i-xbar)*(v-ybar) for i,v in enumerate(vals))
    den=sum((i-xbar)**2 for i in range(len(vals))) or 1.0
    return (num/den)/ybar*100.0

def timeframe_features(candles):
    if len(candles)<35:
        return {}
    closes=[c["close"] for c in candles]
    vols=[c["volume"] for c in candles]
    last=closes[-1]
    e9=ema(closes[-60:],9)
    e20=ema(closes[-80:],20)
    e50=ema(closes[-100:],50)
    rrsi=rsi(closes)
    a=atr(candles)
    atr_pct=(a/last*100.0) if last else 0.0
    vol_z=zscore_last(vols)
    slope=slope_pct(closes,12)
    high20=max(c["high"] for c in candles[-20:])
    low20=min(c["low"] for c in candles[-20:])
    pos=0.5 if high20==low20 else (last-low20)/(high20-low20)
    ret4=pct_change(closes[-5],closes[-1]) if len(closes)>=5 else 0.0
    score=0.0
    score += 1.1 if e9>e20 else -1.1
    score += 0.8 if e20>e50 else -0.8
    score += clamp(slope*4.0,-1.5,1.5)
    score += clamp(ret4/max(atr_pct,0.2),-1.2,1.2)*0.6
    if rrsi>=55:
        score += min((rrsi-55)/20,0.8)
    elif rrsi<=45:
        score -= min((45-rrsi)/20,0.8)
    if pos>0.8 and vol_z>0.5:
        score += 0.5
    if pos<0.2 and vol_z>0.5:
        score -= 0.5
    return {
        "last":last,"ema9":e9,"ema20":e20,"ema50":e50,
        "rsi":rrsi,"atr":a,"atr_pct":atr_pct,"volume_z":vol_z,
        "slope_pct_per_bar":slope,"range_position":pos,
        "ret_4":ret4,"score":score
    }

from features import timeframe_features

def test_feature_engine_runs():
    candles=[]
    p=100.0
    for i in range(60):
        p*=1.001
        candles.append({
            "ts":i+1,"open":p*0.999,"high":p*1.002,"low":p*0.998,
            "close":p,"volume":1000+i,"quote_volume":100000
        })
    ft=timeframe_features(candles)
    assert ft
    assert "score" in ft
    assert ft["last"]>0

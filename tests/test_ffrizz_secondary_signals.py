import math

import ffrizz_secondary_signals as ffrizz


def _candles(count=260, start=100.0, step=0.15):
    rows=[]
    price=start
    for i in range(count):
        close=price+step
        rows.append({
            "ts": (i+1)*3600000,
            "open": price,
            "high": close+0.5,
            "low": price-0.5,
            "close": close,
            "volume": 1000+i,
        })
        price=close
    return rows


def test_horizon_profiles_are_fixed_and_cover_requested_secondary_system():
    assert tuple(ffrizz.HORIZON_PROFILES)==("6h","12h","24h","48h","72h","7d")
    assert [ffrizz.HORIZON_PROFILES[h]["forward_bars"] for h in ffrizz.HORIZON_ORDER]==[6,12,24,12,18,42]


def test_pb_ema_channel_is_bullish_above_channel():
    vote=ffrizz._pb_ema_vote(_candles())
    assert vote.available is True
    assert vote.family=="pb_ema"
    assert vote.score>0
    assert "above_200_ema_channel" in vote.reason


def test_inside_bar_breakout_vote_is_directional():
    rows=_candles()
    mother={"ts":999,"open":100,"high":110,"low":90,"close":102,"volume":1}
    inside={"ts":1000,"open":101,"high":108,"low":92,"close":103,"volume":1}
    breakout={"ts":1001,"open":103,"high":113,"low":102,"close":111,"volume":1}
    rows[-3:]=[mother,inside,breakout]
    vote=ffrizz._inside_bar_vote(rows)
    assert vote.score==1.0
    assert vote.reason=="inside_bar_upside_breakout"


def test_fvg_detects_unmitigated_bullish_gap():
    rows=_candles()
    rows[-3]={"ts":1,"open":100,"high":101,"low":99,"close":100,"volume":1}
    rows[-2]={"ts":2,"open":101,"high":106,"low":101,"close":105,"volume":1}
    rows[-1]={"ts":3,"open":106,"high":108,"low":103,"close":107,"volume":1}
    fvg=ffrizz._latest_unmitigated_fvg(rows[-3:])
    assert fvg["direction"]=="LONG"
    assert fvg["low"]==101
    assert fvg["high"]==103
    assert fvg["mitigated"] is False


def test_price_oi_vote_uses_exact_timestamp_overlap_only():
    rows=_candles()
    oi=[]
    for j,c in enumerate(rows[-24:]):
        oi.append({"ts":c["ts"],"value":100000+j*1000})
    vote=ffrizz._oi_vote(rows,oi)
    assert vote.available is True
    assert vote.score>0
    assert vote.reason=="price_and_oi_rising_together"


def test_missing_oi_fails_closed_without_invented_vote():
    vote=ffrizz._oi_vote(_candles(),[])
    assert vote.available is False
    assert vote.score==0.0
    assert vote.reason=="oi_unavailable"


def test_shadow_signal_never_gets_trade_or_broker_authority():
    result=ffrizz.score_shadow_signal(_candles(),[],horizon="24h")
    assert result["research_only"] is True
    assert result["shadow_only"] is True
    assert result["trade_authority"] is False
    assert result["paper_trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_authority"] is False
    assert result["action"] in {"WAIT","SHADOW_BUY","SHADOW_SELL"}


def test_short_history_returns_only_unavailable_families():
    votes=ffrizz.feature_votes(_candles(50),[])
    assert len(votes)==4
    assert all(v.available is False for v in votes)
    result=ffrizz.score_shadow_signal(_candles(50),[],horizon="6h")
    assert result["action"]=="WAIT"


def test_chronological_backtest_is_non_overlapping_and_after_cost():
    rows=_candles(500,step=0.25)
    result=ffrizz.chronological_backtest(rows,horizon="6h",cost_bps=12)
    assert result["research_only"] is True
    assert result["non_overlapping"] is True
    assert result["fixed_rules"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    indices=[row["index"] for row in result["rows"]]
    assert all(b-a>=6 for a,b in zip(indices,indices[1:]))
    for row in result["rows"]:
        assert math.isclose(row["net_pct"],row["gross_pct"]-0.12,rel_tol=0,abs_tol=1e-12)

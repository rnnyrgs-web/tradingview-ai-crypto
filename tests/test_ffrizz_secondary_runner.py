import ffrizz_secondary_runner as runner


def _candles(count=500):
    rows=[]
    p=100.0
    for i in range(count):
        p+=0.2
        rows.append({"ts": (i+1)*3600000, "open":p-0.2, "high":p+0.5, "low":p-0.5, "close":p, "volume":1000+i})
    return rows


def test_aggregate_backtests_weights_by_signal_count():
    result=runner._aggregate_backtests([
        {"signals":10,"accuracy":0.6,"mean_net_pct":1.0},
        {"signals":30,"accuracy":0.8,"mean_net_pct":2.0},
    ])
    assert result["signals"]==40
    assert abs(result["accuracy"]-0.75)<1e-12
    assert abs(result["mean_net_pct"]-1.75)<1e-12


def test_runner_is_shadow_only_and_evaluates_all_horizons(monkeypatch):
    monkeypatch.setattr(runner,"build_universe",lambda:[{"symbol":"BTC-USDT","base":"BTC"}])
    monkeypatch.setattr(runner,"get_history",lambda *args,**kwargs:_candles())
    monkeypatch.setattr(runner,"get_derivatives_history",lambda *args,**kwargs:{"open_interest_history":{"binance":[]}})
    report=runner.run()
    assert report["system"]=="FFRIZZ_SECONDARY_V1"
    assert report["research_only"] is True
    assert report["shadow_only"] is True
    assert report["trade_authority"] is False
    assert report["paper_trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["broker_authority"] is False
    assert [row["horizon"] for row in report["horizon_results"]]==["6h","12h","24h","48h","72h","7d"]


def test_runner_does_not_fabricate_missing_history(monkeypatch):
    monkeypatch.setattr(runner,"build_universe",lambda:[{"symbol":"BTC-USDT","base":"BTC"}])
    def fail(*args,**kwargs):
        raise RuntimeError("source unavailable")
    monkeypatch.setattr(runner,"get_history",fail)
    report=runner.run()
    assert report["failed_history_fetches"]
    for horizon in report["horizon_results"]:
        assert horizon["current_shadow_signals"]==[]
        assert horizon["diagnostic_backtest"]["signals"]==0

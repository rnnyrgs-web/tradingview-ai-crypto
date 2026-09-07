import execution_oos


def _book(slippage=6.0, complete=True):
    def exchange(name):
        fill = {
            "available": True,
            "complete_fill": complete,
            "slippage_bps_vs_mid": slippage,
        }
        return {
            "exchange": name,
            "reliable": True,
            "live_fill_slippage": {
                "research_only": True,
                "available": True,
                "historical": False,
                "estimates": [
                    {"quote_notional": 5000.0, "buy": dict(fill), "sell": dict(fill)}
                ],
            },
        }

    return {
        "research_only": True,
        "reliable": True,
        "live_slippage_source_count": 2,
        "exchanges": [exchange("okx"), exchange("binance")],
    }


def test_snapshot_anchor_requires_two_complete_reliable_sources():
    good = execution_oos.snapshot_round_trip_slippage_bps(_book(7.5), 5000)
    assert good["available"] is True
    assert good["historical"] is False
    assert good["source_count"] == 2
    assert good["observed_round_trip_slippage_bps"] == 15.0

    partial = execution_oos.snapshot_round_trip_slippage_bps(_book(7.5, complete=False), 5000)
    assert partial["available"] is False
    assert partial["reason"] == "incomplete_fill_or_missing_notional"


def test_snapshot_informed_costs_only_expand_conservative_grid():
    anchor = {"available": True, "observed_round_trip_slippage_bps": 40.0}
    costs = execution_oos.execution_stress_costs(anchor, base_cost_bps=12.0)
    assert 12.0 in costs
    assert 36.0 in costs
    assert 40.0 in costs
    assert 60.0 in costs
    assert 80.0 in costs
    assert costs == tuple(sorted(costs))


def test_evaluate_execution_oos_preserves_holdout_path_and_marks_snapshot_nonhistorical(monkeypatch):
    monkeypatch.setattr(
        execution_oos,
        "walk_forward",
        lambda *args, **kwargs: {"ok": True, "selected_threshold": 2.25},
    )
    history = [
        {"ts": i + 1, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}
        for i in range(1000)
    ]
    monkeypatch.setattr(execution_oos, "get_history", lambda *args, **kwargs: history)
    calls = []

    def fake_score(hist, bar, threshold, cost_bps):
        calls.append((len(hist), threshold, cost_bps))
        return [1.0 - cost_bps / 100.0, 0.5 - cost_bps / 100.0]

    monkeypatch.setattr(execution_oos, "_score_history", fake_score)
    result = execution_oos.evaluate_execution_oos(
        "BTC-USDT", bar="1H", bars=1000, order_book=_book(20.0)
    )

    assert result["research_only"] is True
    assert result["same_trade_path_policy"] is True
    assert result["historical_slippage_available"] is False
    assert result["current_snapshot_anchor"]["observed_round_trip_slippage_bps"] == 40.0
    assert result["holdout_candles"] == 200
    assert all(length == 200 and threshold == 2.25 for length, threshold, _ in calls)
    assert max(cost for _, _, cost in calls) == 80.0


def test_no_viable_training_threshold_does_not_touch_live_or_history(monkeypatch):
    monkeypatch.setattr(execution_oos, "walk_forward", lambda *args, **kwargs: {"ok": True})

    def forbidden(*args, **kwargs):
        raise AssertionError("must not fetch execution/history evidence without a selected threshold")

    monkeypatch.setattr(execution_oos, "get_order_book_intelligence", forbidden)
    monkeypatch.setattr(execution_oos, "get_history", forbidden)
    result = execution_oos.evaluate_execution_oos("ETH-USDT", bars=1000)
    assert result["ok"] is True
    assert "No viable training threshold" in result["message"]

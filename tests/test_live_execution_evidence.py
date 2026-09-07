from market_intelligence import liquidation_evidence, live_fill_slippage_estimates, order_book_summary


def test_live_fill_slippage_uses_visible_book_without_extrapolation():
    bids = [[100.0, 10.0], [99.5, 10.0]]
    asks = [[100.2, 5.0], [100.5, 10.0]]
    result = live_fill_slippage_estimates(bids, asks, notionals=(100.0, 1000.0, 10000.0))

    assert result["research_only"] is True
    assert result["historical"] is False
    assert result["available"] is True

    small = result["estimates"][0]
    assert small["buy"]["complete_fill"] is True
    assert small["sell"]["complete_fill"] is True
    assert small["buy"]["slippage_bps_vs_mid"] >= 0
    assert small["sell"]["slippage_bps_vs_mid"] >= 0

    large = result["estimates"][-1]
    assert large["buy"]["complete_fill"] is False
    assert large["buy"]["reason"] == "insufficient_visible_depth"
    assert 0 < large["buy"]["coverage_ratio"] < 1


def test_live_fill_slippage_rejects_crossed_or_empty_book():
    crossed = live_fill_slippage_estimates([[101, 1]], [[100, 1]])
    empty = live_fill_slippage_estimates([], [[100, 1]])
    assert crossed["available"] is False
    assert crossed["reason"] == "invalid_book"
    assert empty["available"] is False


def test_order_book_summary_embeds_research_only_live_slippage():
    bids = [[100 - i * 0.01, 5] for i in range(12)]
    asks = [[100.1 + i * 0.01, 5] for i in range(12)]
    result = order_book_summary(bids, asks, min_levels=10, max_spread_bps=20)
    assert result["reliable"] is True
    assert result["live_fill_slippage"]["research_only"] is True
    assert result["live_fill_slippage"]["historical"] is False
    assert result["live_fill_slippage"]["available"] is True


def test_liquidation_evidence_never_claims_usd_notional():
    result = liquidation_evidence([
        {"side": "sell", "price": "100", "size": "3"},
        {"side": "buy", "price": "110", "size": "2"},
        {"side": "bad", "price": "999", "size": "999"},
    ])
    assert result["research_only"] is True
    assert result["available"] is True
    assert result["event_count"] == 2
    assert result["sell_event_count"] == 1
    assert result["buy_event_count"] == 1
    assert result["sell_raw_size"] == 3.0
    assert result["buy_raw_size"] == 2.0
    assert result["pressure_units_are_usd"] is False
    assert result["sell_pressure_units"] == 300.0
    assert result["buy_pressure_units"] == 220.0


def test_liquidation_evidence_fails_closed_when_no_valid_events():
    result = liquidation_evidence([{"side": "sell", "price": 0, "size": 2}])
    assert result["available"] is False
    assert result["event_count"] == 0
    assert result["reason"] == "no_valid_events"

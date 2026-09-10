from ffrizz_oi_causal_asof_challenger import oi_vote_causal_asof, score_shadow_signal_v3


HOUR = 3_600_000


def _candles(n=12):
    return [{"ts": i * HOUR, "close": 100.0 + i} for i in range(1, n + 1)]


def test_causal_asof_accepts_non_boundary_oi_period_ends_without_future_price():
    candles = _candles()
    # Each observation lands 17 minutes after an hourly candle endpoint. V2 exact
    # equality rejects these; V3 must use only the already-completed endpoint.
    oi = [
        {"ts": (i + 1) * HOUR + 17 * 60_000, "value": 1000.0 + i * 10}
        for i in range(1, 11)
    ]
    vote = oi_vote_causal_asof(candles, oi, lookback=10)
    assert vote.available is True
    assert vote.family == "price_oi_correlation_v3"


def test_causal_asof_never_uses_a_future_candle_endpoint():
    candles = _candles()
    # OI arrives 1 ms before each next endpoint, so only the previous completed
    # endpoint may be used. A future/nearest-neighbour join would change chronology.
    oi = [
        {"ts": (i + 2) * HOUR - 1, "value": 1000.0 + i * 10}
        for i in range(1, 10)
    ]
    vote = oi_vote_causal_asof(candles, oi, lookback=9)
    assert vote.available is True


def test_causal_asof_rejects_reused_price_endpoint_as_ambiguous():
    candles = _candles()
    oi = []
    for i in range(1, 8):
        endpoint = (i + 1) * HOUR
        oi.append({"ts": endpoint + 5 * 60_000, "value": 1000.0 + i})
        if i == 4:
            oi.append({"ts": endpoint + 10 * 60_000, "value": 1000.5 + i})
    vote = oi_vote_causal_asof(candles, oi)
    assert vote.available is False
    assert vote.reason == "ambiguous_reused_price_endpoint"


def test_v3_is_separately_fingerprinted_and_has_no_authority():
    candles = _candles()
    oi = [
        {"ts": (i + 1) * HOUR + 7 * 60_000, "value": 1000.0 + i * 10}
        for i in range(1, 11)
    ]
    signal = score_shadow_signal_v3(candles, oi, horizon="24h", bar="1H")
    assert signal["system"] == "FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF"
    assert signal["version"] == 3
    assert signal["timestamp_alignment"] == "latest_completed_candle_close_at_or_before_oi_period_end"
    assert signal["future_price_used"] is False
    assert signal["nearest_neighbor_used"] is False
    assert signal["interpolation_used"] is False
    assert signal["trade_authority"] is False
    assert signal["paper_trade_authority"] is False
    assert signal["promotion_authority"] is False
    assert signal["broker_authority"] is False

from ffrizz_oi_alignment_challenger import (
    SYSTEM_ID,
    feature_availability_diagnostics,
    oi_vote_close_to_period_end,
    score_shadow_signal_v2,
)


def _candles(count=220, start=1_700_000_000_000, step=3_600_000):
    rows = []
    price = 100.0
    for i in range(count):
        price *= 1.001
        rows.append({
            "ts": start + i * step,
            "open": price - 0.1,
            "high": price + 0.4,
            "low": price - 0.4,
            "close": price,
            "volume": 1_000 + i,
        })
    return rows


def test_v2_matches_candle_close_to_oi_period_end_not_candle_open():
    candles = _candles()
    oi = [
        {"ts": candle["ts"] + 3_600_000, "value": 10_000 + i * 50}
        for i, candle in enumerate(candles[-24:])
    ]
    vote = oi_vote_close_to_period_end(candles, oi, bar="1H")
    assert vote.available is True
    assert vote.family == "price_oi_correlation_v2"
    assert vote.reason == "price_and_oi_rising_together"


def test_v2_rejects_v1_open_timestamp_semantics():
    candles = _candles()
    oi = [
        {"ts": candle["ts"], "value": 10_000 + i * 50}
        for i, candle in enumerate(candles[-24:])
    ]
    vote = oi_vote_close_to_period_end(candles, oi, bar="1H")
    assert vote.available is False
    assert vote.reason == "insufficient_close_to_period_end_overlap"


def test_v2_is_separate_research_only_fingerprint_with_no_authority():
    candles = _candles()
    oi = [
        {"ts": candle["ts"] + 3_600_000, "value": 10_000 + i * 50}
        for i, candle in enumerate(candles[-24:])
    ]
    signal = score_shadow_signal_v2(candles, oi, horizon="24h", bar="1H")
    assert signal["system"] == SYSTEM_ID
    assert signal["system"] != "FFRIZZ_SECONDARY_V1"
    assert signal["timestamp_alignment"] == "completed_candle_close_exactly_equals_oi_period_end"
    assert signal["interpolation_used"] is False
    assert signal["backfill_used"] is False
    assert signal["research_only"] is True
    assert signal["trade_authority"] is False
    assert signal["paper_trade_authority"] is False
    assert signal["promotion_authority"] is False
    assert signal["broker_authority"] is False


def test_feature_availability_diagnostics_are_count_only():
    candles = _candles()
    oi = [
        {"ts": candle["ts"] + 3_600_000, "value": 10_000 + i * 50}
        for i, candle in enumerate(candles[-24:])
    ]
    signal = score_shadow_signal_v2(candles, oi, horizon="24h", bar="1H")
    report = feature_availability_diagnostics({"24h": [signal]})
    assert report["symbol_level_data_exposed"] is False
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["horizons"]["24h"]["signals_scored"] == 1
    assert "price_oi_correlation_v2:available" in report["horizons"]["24h"]["family_counts"]

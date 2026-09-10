from ffrizz_oi_alignment_challenger import oi_vote_close_to_period_end


def test_nearby_but_not_exact_oi_timestamp_is_not_matched():
    candles = [
        {"ts": 1_700_000_000_000 + i * 3_600_000, "close": 100 + i}
        for i in range(12)
    ]
    oi = [
        {"ts": candle["ts"] + 3_600_000 + 1, "value": 1000 + i}
        for i, candle in enumerate(candles)
    ]
    vote = oi_vote_close_to_period_end(candles, oi, bar="1H")
    assert vote.available is False
    assert vote.reason == "insufficient_close_to_period_end_overlap"

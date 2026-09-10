from ffrizz_oi_alignment_challenger import oi_vote_close_to_period_end


def test_duplicate_oi_period_end_is_rejected():
    candles = [
        {"ts": 1_700_000_000_000 + i * 3_600_000, "close": 100 + i}
        for i in range(10)
    ]
    endpoint = candles[-1]["ts"] + 3_600_000
    oi = [{"ts": endpoint, "value": 1000}, {"ts": endpoint, "value": 1001}]
    vote = oi_vote_close_to_period_end(candles, oi, bar="1H")
    assert vote.available is False
    assert vote.reason == "ambiguous_duplicate_oi_period_end"

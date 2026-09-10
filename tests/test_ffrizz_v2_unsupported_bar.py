from ffrizz_oi_alignment_challenger import oi_vote_close_to_period_end


def test_v2_unsupported_bar_fails_closed():
    vote = oi_vote_close_to_period_end(
        [{"ts": 1_700_000_000_000, "close": 100}],
        [{"ts": 1_700_014_400_000, "value": 1000}],
        bar="4H",
    )
    assert vote.available is False
    assert vote.reason == "unsupported_bar"

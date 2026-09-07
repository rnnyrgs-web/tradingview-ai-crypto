from evaluator import nearest_close


def test_nearest_close_fails_closed_without_post_horizon_evidence():
    candles = [
        {"ts": 1_000, "close": 100.0},
        {"ts": 2_000, "close": 101.0},
    ]

    assert nearest_close(candles, 3_000) is None

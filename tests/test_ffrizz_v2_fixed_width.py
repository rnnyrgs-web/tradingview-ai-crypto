from ffrizz_oi_alignment_challenger import SUPPORTED_BAR_MS


def test_v2_1h_width_is_exactly_one_hour():
    assert SUPPORTED_BAR_MS == {"1H": 3_600_000}

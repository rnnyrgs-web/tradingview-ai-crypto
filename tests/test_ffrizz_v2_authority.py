from ffrizz_oi_alignment_challenger import score_shadow_signal_v2


def test_v2_never_creates_trade_authority():
    signal = score_shadow_signal_v2([], [], horizon="24h", bar="1H")
    assert signal["research_only"] is True
    assert signal["trade_authority"] is False
    assert signal["paper_trade_authority"] is False
    assert signal["promotion_authority"] is False
    assert signal["broker_authority"] is False

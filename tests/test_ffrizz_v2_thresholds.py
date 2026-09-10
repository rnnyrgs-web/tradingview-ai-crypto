from ffrizz_secondary_signals import FIXED_SIGNAL_THRESHOLD, FIXED_STRONG_THRESHOLD
from ffrizz_oi_alignment_challenger import score_shadow_signal_v2


def test_v2_uses_existing_predeclared_thresholds_without_tuning():
    assert FIXED_SIGNAL_THRESHOLD == 2.25
    assert FIXED_STRONG_THRESHOLD == 3.25
    assert callable(score_shadow_signal_v2)

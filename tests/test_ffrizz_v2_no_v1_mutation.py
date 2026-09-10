from ffrizz_secondary_signals import score_shadow_signal
from ffrizz_oi_alignment_challenger import SYSTEM_ID


def test_v2_does_not_replace_v1_system_identity():
    candles = [
        {"ts": 1_700_000_000_000 + i * 3_600_000, "open": 100+i, "high": 101+i, "low": 99+i, "close": 100+i, "volume": 1}
        for i in range(220)
    ]
    v1 = score_shadow_signal(candles, [], horizon="24h")
    assert v1["system"] == "FFRIZZ_SECONDARY_V1"
    assert v1["system"] != SYSTEM_ID

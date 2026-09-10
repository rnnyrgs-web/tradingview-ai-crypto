from ffrizz_oi_alignment_challenger import SYSTEM_ID


def test_v2_identity_is_not_v1():
    assert SYSTEM_ID != "FFRIZZ_SECONDARY_V1"

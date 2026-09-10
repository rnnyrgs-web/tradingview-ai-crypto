from ffrizz_oi_alignment_challenger import SYSTEM_ID, SYSTEM_VERSION


def test_v2_metadata_is_immutable_and_distinct():
    assert SYSTEM_ID == "FFRIZZ_SECONDARY_V2_OI_CLOSE_END"
    assert SYSTEM_VERSION == 2

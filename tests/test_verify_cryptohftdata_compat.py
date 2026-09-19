from tools.verify_cryptohftdata_preflight_compat import (
    ZSTD_MAGIC,
    decode_legacy_external_zstd,
    is_legacy_external_zstd,
)


def test_detects_legacy_external_zstd_without_touching_normal_parquet():
    legacy = ZSTD_MAGIC + b"payload"
    parquet = b"PAR1payloadPAR1"
    assert is_legacy_external_zstd(legacy)
    assert not is_legacy_external_zstd(parquet)
    assert decode_legacy_external_zstd(parquet) is parquet

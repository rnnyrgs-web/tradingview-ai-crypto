#!/usr/bin/env python3
"""Compatibility runner for legacy externally-zstd CryptoHFTData objects.

CryptoHFTData documents that objects collected before 2026-08-19 used a
`.parquet.zst` storage format.  Its REST `/download` endpoint accepts either
spelling for any date, so requesting a legacy object with a `.parquet` path can
still return an externally-zstd-compressed payload.  This runner preserves the
raw-byte SHA-256 computed by the frozen verifier while transparently decoding
that legacy transport wrapper before PyArrow parses the Parquet payload.
"""

from __future__ import annotations

from tools import verify_cryptohftdata_preflight as base

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def is_legacy_external_zstd(data: bytes) -> bool:
    return data.startswith(ZSTD_MAGIC)


def decode_legacy_external_zstd(data: bytes) -> bytes:
    if not is_legacy_external_zstd(data):
        return data
    import zstandard as zstd  # type: ignore

    return zstd.ZstdDecompressor().decompress(data)


_original_read_parquet = base.read_parquet
_original_analyze_file = base.analyze_file


def _read_parquet_compat(data: bytes):
    return _original_read_parquet(decode_legacy_external_zstd(data))


def _analyze_file_compat(symbol: str, data_type: str, path: str, body: bytes, acquired_at: str):
    result = _original_analyze_file(symbol, data_type, path, body, acquired_at)
    result["transport_encoding"] = "external_zstd_legacy" if is_legacy_external_zstd(body) else "parquet_internal_compression"
    return result


base.read_parquet = _read_parquet_compat
base.analyze_file = _analyze_file_compat


if __name__ == "__main__":
    raise SystemExit(base.main())

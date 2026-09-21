from __future__ import annotations

import copy
import json

import pytest

from research_artifact import sha256_hex
from strategy_dataset_preflight import (
    DATASET_PATH,
    FROZEN_DATASET_GIT_BLOB_SHA1,
    FROZEN_DATASET_SHA256,
    _parse_development_view,
    qualify_cohort001_dataset,
)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key).lower()
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _row(ts: int, *, poisoned: bool = False) -> dict:
    return {
        "ts": ts,
        "open": "POISON_PROTECTED_VALUE" if poisoned else 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10.0,
        "quote_volume": 1000.0,
    }


def _synthetic_dataset(*, poison_development: bool = False, poison_protected: bool = False) -> bytes:
    development_ts = 1_788_217_200_000  # 2026-08-31T23:00:00Z
    protected_ts = development_ts + 3_600_000
    instruments = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    payload = {
        "source": "synthetic isolation fixture",
        "bar": "1H",
        "fixed_instruments": instruments,
        "histories": {
            instrument: [
                _row(development_ts, poisoned=poison_development),
                _row(protected_ts, poisoned=poison_protected),
            ]
            for instrument in instruments
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def test_committed_selection_dataset_is_qualified_without_economic_outcomes():
    receipt = qualify_cohort001_dataset()

    assert receipt["schema_version"] == 2
    assert receipt["status"] == "QUALIFIED_DEVELOPMENT_ONLY"
    assert receipt["source_git_blob_sha1"] == FROZEN_DATASET_GIT_BLOB_SHA1
    assert receipt["source_dataset_sha256"] == FROZEN_DATASET_SHA256
    assert receipt["development_end_utc"] == "2026-08-31T23:00:00+00:00"
    assert receipt["protected_start_utc"] == "2026-09-01T00:00:00+00:00"
    assert receipt["development_common_timestamps"] == 11563
    assert receipt["development_rows_total"] == 34689
    assert receipt["protected_rows_excluded_total"] == 1308
    assert receipt["checks"]["exact_committed_compressed_git_blob"] is True
    assert receipt["checks"]["protected_ohlcv_json_decoded"] is False
    assert receipt["economic_outcomes_computed"] is False
    assert receipt["strategy_signals_computed"] is False
    assert receipt["untouched_oos_opened"] is False
    assert receipt["genuine_forward_opened"] is False
    assert receipt["trade_authority"] is False
    assert receipt["broker_connected"] is False

    for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"):
        assert receipt["per_instrument"][instrument]["source_rows"] == 11999
        assert receipt["per_instrument"][instrument]["development_rows"] == 11563
        assert receipt["per_instrument"][instrument]["protected_rows_excluded"] == 436
        assert receipt["per_instrument"][instrument]["development_end_utc"] == "2026-08-31T23:00:00+00:00"


def test_receipt_is_canonical_and_contains_no_ohlcv_or_outcome_payload_fields():
    receipt = qualify_cohort001_dataset()
    unsigned = copy.deepcopy(receipt)
    signature = unsigned.pop("receipt_sha256")
    assert signature == sha256_hex(unsigned)

    forbidden = {"open", "high", "low", "close", "volume", "quote_volume", "return", "pnl", "profit_factor"}
    assert forbidden.isdisjoint(set(_walk_keys(receipt)))


def test_altered_compressed_source_cannot_redefine_authoritative_identity(tmp_path):
    # Mutate only compressed bytes; do not decompress or inspect canonical market values.
    altered = bytearray(DATASET_PATH.read_bytes())
    altered[-1] ^= 1
    path = tmp_path / "altered-dataset.json.gz"
    path.write_bytes(bytes(altered))

    with pytest.raises(RuntimeError, match="immutable compressed selection dataset identity mismatch"):
        qualify_cohort001_dataset(path)


def test_protected_ohlcv_poison_is_never_decoded_but_development_poison_fails():
    development_ts = 1_788_217_200_000
    protected_ts = development_ts + 3_600_000

    metadata, development, timestamps = _parse_development_view(
        _synthetic_dataset(poison_protected=True),
        cutoff_ms=development_ts,
        protected_ms=protected_ts,
    )
    assert metadata["bar"] == "1H"
    assert set(development) == {"BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"}
    assert all(len(rows) == 1 for rows in development.values())
    assert all(series == [development_ts, protected_ts] for series in timestamps.values())

    with pytest.raises((ValueError, TypeError)):
        _parse_development_view(
            _synthetic_dataset(poison_development=True),
            cutoff_ms=development_ts,
            protected_ms=protected_ts,
        )


def test_development_window_cannot_overlap_protected_evidence():
    with pytest.raises(ValueError, match="strictly before protected"):
        qualify_cohort001_dataset(
            development_end_utc="2026-09-01T00:00:00+00:00",
            protected_start_utc="2026-09-01T00:00:00+00:00",
        )


def test_development_and_protected_boundary_must_be_contiguous_hourly():
    with pytest.raises(ValueError, match="contiguous hourly chronology"):
        qualify_cohort001_dataset(
            development_end_utc="2026-08-31T22:00:00+00:00",
            protected_start_utc="2026-09-01T00:00:00+00:00",
        )

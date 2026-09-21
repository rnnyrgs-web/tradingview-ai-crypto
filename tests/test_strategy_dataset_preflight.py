from __future__ import annotations

import copy

import pytest

from research_artifact import sha256_hex
from strategy_dataset_preflight import (
    FROZEN_DATASET_SHA256,
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


def test_committed_selection_dataset_is_qualified_without_economic_outcomes():
    receipt = qualify_cohort001_dataset()

    assert receipt["status"] == "QUALIFIED_DEVELOPMENT_ONLY"
    assert receipt["source_dataset_sha256"] == FROZEN_DATASET_SHA256
    assert receipt["development_end_utc"] == "2026-08-31T23:00:00+00:00"
    assert receipt["protected_start_utc"] == "2026-09-01T00:00:00+00:00"
    assert receipt["development_common_timestamps"] == 11563
    assert receipt["development_rows_total"] == 34689
    assert receipt["protected_rows_excluded_total"] == 1308
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


def test_wrong_dataset_identity_fails_closed_before_screening():
    with pytest.raises(RuntimeError, match="dataset identity mismatch"):
        qualify_cohort001_dataset(expected_dataset_sha256="0" * 64)


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

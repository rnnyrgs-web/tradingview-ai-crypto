from __future__ import annotations

import gzip
import io
import json
from pathlib import Path

import pytest

from tardis_l2_qualification import EXPECTED_COLUMNS, parse_incremental_l2_csv, reconstruct_books
from tardis_l2_real_sample import (
    PASS_STATUS,
    qualify_gzip_sample,
    summarize_real_sample_stream,
)


HEADER = ",".join(EXPECTED_COLUMNS)


def _csv(*rows: str) -> str:
    return HEADER + "\n" + "\n".join(rows) + "\n"


def _fixture() -> str:
    return _csv(
        "binance,BTCUSDT,900,100,false,bid,99,9",
        "binance,BTCUSDT,1000,110,true,bid,100,2",
        "binance,BTCUSDT,1000,110,true,bid,99,3",
        "binance,BTCUSDT,1000,110,true,ask,101,4",
        "binance,BTCUSDT,1000,110,true,ask,102,5",
        "binance,BTCUSDT,1020,120,false,bid,100,4",
        "binance,BTCUSDT,1020,120,false,ask,101,0",
        "binance,BTCUSDT,1030,130,false,bid,98,6",
        "binance,BTCUSDT,1030,130,false,ask,103,7",
        "binance,BTCUSDT,1040,140,false,bid,97,2",
        "binance,BTCUSDT,1040,140,false,ask,104,2",
    )


def test_streaming_summary_matches_bounded_adapter_on_real_shape_fixture():
    raw = _fixture()
    bounded = reconstruct_books(
        parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")
    )
    summary = summarize_real_sample_stream(
        io.StringIO(raw), expected_exchange="binance", expected_symbol="BTCUSDT"
    )

    assert summary.row_count == 11
    assert summary.message_count == 5
    assert summary.ignored_pre_snapshot_rows == 1
    assert summary.ignored_pre_snapshot_messages == 1
    assert summary.snapshot_message_count == 1
    assert summary.incremental_message_count == 3
    assert summary.reconstructed_state_count == len(bounded) == 4
    assert summary.reset_count == 1
    assert summary.crossed_state_count == 0
    assert summary.gap_free_support_interval_count == 3
    assert summary.exact_instant_only_state_count == 1
    assert summary.canary_reconstructed_state_count >= 3
    assert summary.max_bid_levels >= 2
    assert summary.max_ask_levels >= 1


def test_streaming_summary_rejects_mixed_snapshot_message():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,100,1",
        "binance,BTCUSDT,1000,110,false,ask,101,1",
    )
    with pytest.raises(ValueError, match="cannot mix"):
        summarize_real_sample_stream(
            io.StringIO(raw), expected_exchange="binance", expected_symbol="BTCUSDT"
        )


def test_streaming_summary_rejects_wrong_provider_identity():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,100,1",
        "binance,BTCUSDT,1000,110,true,ask,101,1",
    )
    with pytest.raises(ValueError, match="symbol mismatch"):
        summarize_real_sample_stream(
            io.StringIO(raw), expected_exchange="binance", expected_symbol="ETHUSDT"
        )


def test_gzip_receipt_is_provider_adapter_only(tmp_path: Path):
    sample = tmp_path / "sample.csv.gz"
    with gzip.open(sample, "wt", encoding="utf-8", newline="") as handle:
        handle.write(_fixture())

    receipt = qualify_gzip_sample(
        sample,
        source_url="https://datasets.tardis.dev/example.csv.gz",
        expected_exchange="binance",
        expected_symbol="BTCUSDT",
        retrieved_at="2026-09-22T22:00:00Z",
        commit_sha="a" * 40,
    )

    assert receipt["status"] == PASS_STATUS
    assert receipt["authority"] == "PROVIDER_ADAPTER_ONLY"
    assert receipt["outcomes_opened"] is False
    assert receipt["strict_tradability_established"] is False
    assert receipt["candidate_authority"] is False
    assert receipt["model_fitting_authority"] is False
    assert receipt["broker_connected"] is False
    assert receipt["live_trading"] is False
    assert len(receipt["compressed_sha256"]) == 64
    assert receipt["compressed_bytes"] > 0
    json.dumps(receipt)

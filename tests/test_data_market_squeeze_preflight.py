import hashlib
import json
from pathlib import Path

import pytest

from squeeze_retention_data_preflight import (
    HOUR_NS, START_NS, audit_cache, audit_rows, available_asof, sample_objects,
)


def row(family="liquidations", **updates):
    result = {"symbol": "BTCUSDT", "received_time": START_NS + 2_000_000_000}
    if family == "liquidations":
        result.update(event_time=(START_NS // 1_000_000) + 1000,
                      trade_time=START_NS // 1_000_000, side="SELL",
                      quantity="1", price="10", average_price="10",
                      filled_quantity="1")
    elif family == "open_interest":
        result.update(timestamp=START_NS // 1_000_000,
                      sum_open_interest="100", sum_open_interest_value="1000")
    else:
        result.update(event_time=START_NS // 1_000_000, mark_price="10",
                      index_price="10", funding_rate="-0.001",
                      next_funding_time=(START_NS + HOUR_NS) // 1_000_000)
    result.update(updates)
    return result


@pytest.mark.parametrize("family", ["liquidations", "open_interest", "mark_price"])
def test_valid_structure_never_authorizes_scientific_screen(family):
    report = audit_rows([row(family)], "BTCUSDT", family)
    assert report["errors"] == {}
    assert report["row_count"] == 1
    assert report["feature_authorized"] is False


@pytest.mark.parametrize("change,error", [
    ({"received_time": START_NS // 1_000_000}, "timestamp_unit_or_range"),
    ({"event_time": START_NS}, "timestamp_unit_or_range"),
    ({"event_time": True}, "timestamp_type"),
    ({"symbol": "ETHUSDT"}, "wrong_symbol"),
    ({"received_time": START_NS + HOUR_NS}, "receipt_outside_hour"),
    ({"received_time": START_NS - 1}, "receipt_outside_hour"),
    ({"event_time": START_NS // 1_000_000 + 3000}, "event_after_receipt"),
    ({"trade_time": START_NS // 1_000_000 + 1500}, "trade_after_event"),
    ({"quantity": "NaN"}, "invalid_numeric"),
    ({"price": "-1"}, "invalid_numeric"),
    ({"side": "LONG"}, "invalid_side"),
])
def test_malformed_rows_fail_closed(change, error):
    assert error in audit_rows([row(**change)], "BTCUSDT", "liquidations")["errors"]


def test_missing_fields_and_empty_file_are_not_zero_liquidation_evidence():
    assert "missing_fields" in audit_rows([{}], "BTCUSDT", "liquidations")["errors"]
    assert "empty_file" in audit_rows([], "BTCUSDT", "liquidations")["errors"]


def test_oi_repeats_and_old_snapshots_are_reported_without_backdating_availability():
    old = row("open_interest", timestamp=(START_NS - 48 * HOUR_NS) // 1_000_000)
    newer_receipt = dict(old, received_time=old["received_time"] + 1_000_000_000)
    report = audit_rows([old, newer_receipt, old], "BTCUSDT", "open_interest")
    assert report["unique_event_timestamps"] == 1
    assert report["repeated_event_timestamps"] == 2
    assert report["duplicate_rows"] == 1
    assert report["receipt_order_inversions"] == 1
    assert report["event_age_ms_max"] == 48 * 3_600_000 + 3000
    assert report["events_before_receipt_hour"] == 3
    assert report["feature_authorized"] is False


def test_asof_requires_explicit_archive_publication_and_inclusive_boundary():
    rows = [row()]
    receipt = rows[0]["received_time"]
    publication = START_NS + 2 * HOUR_NS
    with pytest.raises(ValueError, match="publication"):
        available_asof(rows, receipt, None)
    with pytest.raises(ValueError, match="receipt"):
        available_asof(rows, receipt, receipt - 1)
    assert available_asof(rows, publication - 1, publication) == []
    assert available_asof(rows, publication, publication) == rows


def fixture_cache(tmp_path):
    entries = []
    for spec in sample_objects():
        data = json.dumps([row(spec["family"], symbol=spec["symbol"])]).encode()
        (tmp_path / spec["file"]).write_bytes(data)
        entries.append(dict(spec, status="downloaded", http_status=200,
                            acquired_at="2026-09-19T05:00:00+00:00",
                            size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    (tmp_path / "manifest.json").write_text(json.dumps(entries))
    return entries


def read_json(path):
    return json.loads(path.read_bytes())


def test_replay_checks_all_nine_hashes_and_never_promotes_sample(tmp_path):
    fixture_cache(tmp_path)
    report = audit_cache(tmp_path, reader=read_json)
    assert report["verified_objects"] == 9
    assert report["status"] == "INSUFFICIENT_FOR_FROZEN_SCREEN"
    assert "archive_publication_unproved" in report["blockers"]
    assert "historical_coverage_unproved" in report["blockers"]


@pytest.mark.parametrize("failure", ["tamper", "missing", "duplicate", "path", "source", "time", "404"])
def test_cache_corruption_missingness_and_manifest_identity_fail_closed(tmp_path, failure):
    entries = fixture_cache(tmp_path)
    first = entries[0]
    if failure == "tamper":
        (tmp_path / first["file"]).write_bytes(b"modified")
    elif failure == "missing":
        entries.pop(0)
    elif failure == "duplicate":
        entries.append(dict(first))
    elif failure == "path":
        first["file"] = "../outside.parquet"
    elif failure == "source":
        first["url"] = "https://wrong-source.invalid/data"
    elif failure == "time":
        first["acquired_at"] = "2026-09-19T05:00:00"
    else:
        first.update(status="unavailable", http_status=404)
    (tmp_path / "manifest.json").write_text(json.dumps(entries))
    report = audit_cache(tmp_path, reader=read_json)
    assert report["verified_objects"] < 9
    assert "sample_integrity_or_structure_failed" in report["blockers"]
    assert report["status"] == "INSUFFICIENT_FOR_FROZEN_SCREEN"


SAMPLE = Path(__file__).resolve().parents[1] / "research_data/squeeze_preflight/20260902_12"


def test_committed_sample_bytes_match_acquisition_manifest():
    entries = json.loads((SAMPLE / "manifest.json").read_text())
    assert len(entries) == 9
    assert sum(entry["size_bytes"] for entry in entries) < 32 * 1024 * 1024
    for entry, expected in zip(entries, sample_objects()):
        assert all(entry[key] == value for key, value in expected.items())
        data = (SAMPLE / entry["file"]).read_bytes()
        assert len(data) == entry["size_bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_real_parquet_replay_exactly_matches_committed_audit():
    pytest.importorskip("pyarrow")
    assert audit_cache(SAMPLE) == json.loads((SAMPLE / "audit.json").read_text())

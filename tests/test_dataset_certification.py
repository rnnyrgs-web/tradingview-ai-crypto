import hashlib
import json

from dataset_certification import certify_dataset_manifest, certify_dataset_snapshot


def manifest():
    return {
        "dataset_id": "kraken-btc-1h-v1",
        "source": "kraken",
        "venue": "spot",
        "symbol": "BTC/USD",
        "timezone": "UTC",
        "start_timestamp": "2025-01-01T00:00:00+00:00",
        "end_timestamp": "2025-12-31T23:00:00+00:00",
        "received_timestamp_available": False,
        "fields": ["open", "high", "low", "close", "volume"],
        "missing_periods": [],
        "duplicate_timestamps": 0,
        "out_of_order_records": 0,
        "impossible_ohlc_records": 0,
        "stale_records": 0,
        "future_universe_membership": False,
        "future_feature_use": False,
        "point_in_time_universe": True,
        "content_sha256": "abc123",
    }


def test_good_manifest_certifies_and_hashes():
    result = certify_dataset_manifest(manifest())
    assert result["certified"] is True
    assert len(result["dataset_sha256"]) == 64
    assert result["failures"] == []


def test_future_feature_use_fails_closed():
    value = manifest()
    value["future_feature_use"] = True
    result = certify_dataset_manifest(value)
    assert result["certified"] is False
    assert "future_feature_use" in result["failures"]


def test_non_utc_or_non_point_in_time_manifest_fails_closed():
    value = manifest()
    value["timezone"] = "America/New_York"
    value["point_in_time_universe"] = False
    result = certify_dataset_manifest(value)
    assert result["certified"] is False
    assert "timezone_not_utc" in result["failures"]
    assert "point_in_time_universe_missing" in result["failures"]


def test_snapshot_content_must_match_manifest_hash_and_market_invariants():
    snapshot = {"series": [{
        "symbol": "BTC/USD", "bar": "1H", "rows": [
            {"ts": 1735689600000, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 5},
            {"ts": 1735693200000, "open": 101, "high": 103, "low": 100, "close": 102, "volume": 6},
        ],
    }]}
    value = manifest()
    value["start_timestamp"] = "2025-01-01T00:00:00+00:00"
    value["end_timestamp"] = "2025-01-01T01:00:00+00:00"
    value["content_sha256"] = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()
    result = certify_dataset_snapshot(value, snapshot)
    assert result["certified"] is True
    assert result["snapshot_verified"] is True

    snapshot["series"][0]["rows"][1]["close"] = 999
    tampered = certify_dataset_snapshot(value, snapshot)
    assert tampered["certified"] is False
    assert "snapshot_content_hash_mismatch" in tampered["failures"]

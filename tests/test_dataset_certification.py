from dataset_certification import certify_dataset_manifest


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

import continuous_coordinator as coordinator


def test_observability_log_payload_exposes_bounded_ffrizz_collection_summary():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "last_exit_code": 0,
                "elapsed_seconds": 12.5,
                "updated_at_ms": 12345,
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "generated_at": "2026-09-10T10:00:00+00:00",
                        "eligible_shadow_forecasts": 4,
                        "non_overlapping_full_horizon_buckets": True,
                        "wait_rows_persisted": False,
                        "historical_oi_backfill_used": False,
                        "prediction_ledger_rows": [{"sensitive": "must-not-leak"}],
                        "trade_authority": False,
                        "promotion_authority": False,
                    }
                },
            }
        }
    }

    payload = coordinator.observability_log_payload(army)
    ffrizz = payload["ffrizz_forward"]
    assert ffrizz == {
        "worker_exit": 0,
        "worker_elapsed_s": 12.5,
        "updated_at_ms": 12345,
        "collection_ok": True,
        "error_type": None,
        "generated_at": "2026-09-10T10:00:00+00:00",
        "eligible_shadow_forecasts": 4,
        "non_overlapping_full_horizon_buckets": True,
        "wait_rows_persisted": False,
        "historical_oi_backfill_used": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    assert "prediction_ledger_rows" not in str(ffrizz)
    assert "sensitive" not in str(ffrizz)
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["signal_authority"] is False


def test_observability_log_payload_reports_ffrizz_collection_failure_without_detail_leakage():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "last_exit_code": 0,
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": False,
                        "error_type": "HTTPStatusError",
                        "error_detail": "do-not-log-raw-detail",
                    }
                },
            }
        }
    }

    ffrizz = coordinator.observability_log_payload(army)["ffrizz_forward"]
    assert ffrizz["collection_ok"] is False
    assert ffrizz["error_type"] == "HTTPStatusError"
    assert "error_detail" not in str(ffrizz)
    assert "do-not-log-raw-detail" not in str(ffrizz)


def test_observability_log_payload_handles_missing_ffrizz_evidence():
    ffrizz = coordinator.observability_log_payload(None)["ffrizz_forward"]
    assert ffrizz["worker_exit"] is None
    assert ffrizz["collection_ok"] is None
    assert ffrizz["eligible_shadow_forecasts"] is None
    assert ffrizz["trade_authority"] is False
    assert ffrizz["promotion_authority"] is False


def test_observability_log_payload_rejects_malformed_ffrizz_count():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "eligible_shadow_forecasts": True,
                    }
                }
            }
        }
    }
    ffrizz = coordinator.observability_log_payload(army)["ffrizz_forward"]
    assert ffrizz["eligible_shadow_forecasts"] is None

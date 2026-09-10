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
                        "abstention_diagnostics": {
                            "diagnostic_only": True,
                            "thresholds_unchanged": True,
                            "backfill_used": False,
                            "signals_scored": 72,
                            "action_counts": {"WAIT": 68, "SHADOW_BUY": 3, "SHADOW_SELL": 1},
                            "wait_gate_counts": {
                                "insufficient_directional_agreement": 50,
                                "score_below_predeclared_threshold": 18,
                                "unexpected_wait_state": 0,
                            },
                            "available_family_count_distribution": {"3": 48, "4": 24},
                            "family_unavailable_counts": {"price_oi_correlation:oi_unavailable": 24},
                        },
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
        "abstention_diagnostic_only": True,
        "abstention_thresholds_unchanged": True,
        "abstention_backfill_used": False,
        "signals_scored": 72,
        "action_counts": {"WAIT": 68, "SHADOW_BUY": 3, "SHADOW_SELL": 1},
        "wait_gate_counts": {
            "insufficient_directional_agreement": 50,
            "score_below_predeclared_threshold": 18,
            "unexpected_wait_state": 0,
        },
        "available_family_count_distribution": {"3": 48, "4": 24},
        "v2_oi_alignment_feature_availability": None,
        "trade_authority": False,
        "promotion_authority": False,
    }
    assert "prediction_ledger_rows" not in str(ffrizz)
    assert "family_unavailable_counts" not in str(ffrizz)
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
    assert ffrizz["signals_scored"] is None
    assert ffrizz["action_counts"] == {}
    assert ffrizz["wait_gate_counts"] == {}
    assert ffrizz["v2_oi_alignment_feature_availability"] is None
    assert ffrizz["trade_authority"] is False
    assert ffrizz["promotion_authority"] is False


def test_observability_log_payload_rejects_malformed_ffrizz_count_and_unlisted_diagnostic_keys():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "eligible_shadow_forecasts": True,
                        "abstention_diagnostics": {
                            "signals_scored": "72",
                            "action_counts": {"WAIT": 4, "secret_action": 99},
                            "wait_gate_counts": {"unexpected_wait_state": 0, "raw_error_secret": 8},
                            "available_family_count_distribution": {"3": 4, "secret": 100},
                        },
                    }
                }
            }
        }
    }
    ffrizz = coordinator.observability_log_payload(army)["ffrizz_forward"]
    assert ffrizz["eligible_shadow_forecasts"] is None
    assert ffrizz["signals_scored"] is None
    assert ffrizz["action_counts"] == {"WAIT": 4}
    assert ffrizz["wait_gate_counts"] == {"unexpected_wait_state": 0}
    assert ffrizz["available_family_count_distribution"] == {"3": 4}
    assert ffrizz["v2_oi_alignment_feature_availability"] is None
    assert "secret" not in str(ffrizz)
    assert "raw_error" not in str(ffrizz)

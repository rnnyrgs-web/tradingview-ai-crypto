import continuous_coordinator as coordinator


def test_coordinator_reallowlists_only_fixed_oi_source_counts():
    raw = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "eligible_shadow_forecasts": 0,
                        "abstention_diagnostics": {},
                        "oi_source_diagnostics": {
                            "diagnostic_only": True,
                            "source": "MUST_NOT_ESCAPE",
                            "acquisition_attempts": 12,
                            "status_counts": {
                                "http_error": 11,
                                "available": 1,
                                "BTCUSDT": 999,
                            },
                            "raw_error": "secret endpoint text",
                        },
                    }
                }
            }
        },
        "supervisor": {},
    }

    bounded = coordinator.observability_log_payload(raw)["ffrizz_forward"]["oi_source_diagnostics"]

    assert bounded["source"] == "binance_open_interest_history"
    assert bounded["acquisition_attempts"] == 12
    assert bounded["status_counts"] == {"available": 1, "http_error": 11}
    assert bounded["extra_requests_added"] == 0
    assert bounded["symbol_level_data_exposed"] is False
    assert "BTC" not in repr(bounded)
    assert "secret" not in repr(bounded)
    assert "MUST_NOT_ESCAPE" not in repr(bounded)
    assert bounded["trade_authority"] is False
    assert bounded["promotion_authority"] is False

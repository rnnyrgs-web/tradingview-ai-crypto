from continuous_coordinator import observability_log_payload


def test_ffrizz_failure_stage_and_status_class_cross_final_boundary_only_when_allowlisted():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": False,
                        "error_type": "RuntimeError",
                        "error_stage": "prediction_ledger_persistence",
                        "http_status_class": "http_4xx",
                        "raw_error": "must-not-cross-boundary",
                    }
                }
            }
        },
        "supervisor": {"healthy": True},
    }

    forward = observability_log_payload(army)["ffrizz_forward"]

    assert forward["error_type"] == "RuntimeError"
    assert forward["error_stage"] == "prediction_ledger_persistence"
    assert forward["http_status_class"] == "http_4xx"
    assert "raw_error" not in forward
    assert "must-not-cross-boundary" not in repr(forward)


def test_ffrizz_failure_stage_and_status_class_fail_closed_on_unknown_values():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": False,
                        "error_type": "RuntimeError",
                        "error_stage": "arbitrary-provider-detail",
                        "http_status_class": "secret-status",
                    }
                }
            }
        },
        "supervisor": {"healthy": True},
    }

    forward = observability_log_payload(army)["ffrizz_forward"]

    assert forward["error_stage"] is None
    assert forward["http_status_class"] is None

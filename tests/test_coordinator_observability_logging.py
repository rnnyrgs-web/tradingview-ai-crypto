import continuous_coordinator as coordinator


def test_observability_log_payload_is_bounded_and_non_authoritative():
    army = {
        "observability": {
            "cache": {
                "reads_observed": 10,
                "hit_rate": 0.7,
                "rejection_rate": 0.1,
                "read_latency_ms": {"p50": 1.2, "p95": 3.4},
            },
            "history_network": {
                "fetches": 5,
                "failures": 1,
                "latency_ms": {"p50": 800.0, "p95": 2400.0},
                "avg_requests_per_fetch": 12.0,
            },
            "workers": {
                "completed": 20,
                "failed": 2,
                "timeouts": 1,
                "failure_rate": 0.1,
            },
            "acc002": {
                "cross-asset-rank-24h": {
                    "last_exit_code": 0,
                    "elapsed_seconds": 42.5,
                    "updated_at_ms": 123,
                    "latest_evidence": {
                        "selected_evaluation": {
                            "acc002_research_pass": False,
                            "acc011_survivorship_pass": False,
                            "eligible_for_promotion_review": False,
                            "raw_bootstrap_samples": [1, 2, 3],
                        }
                    },
                },
                "cross-asset-rank-7d": {},
            },
        }
    }

    payload = coordinator.observability_log_payload(army)
    assert payload["network_p50_ms"] == 800.0
    assert payload["network_p95_ms"] == 2400.0
    assert payload["acc002_24h"]["elapsed_s"] == 42.5
    assert payload["acc002_24h"]["acc002_pass"] is False
    assert "raw_bootstrap_samples" not in str(payload)
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["signal_authority"] is False


def test_observability_log_payload_handles_missing_state():
    payload = coordinator.observability_log_payload(None)
    assert payload["network_p50_ms"] is None
    assert payload["worker_completed"] is None
    assert payload["acc002_24h"]["promotion_review"] is None
    assert payload["trade_authority"] is False

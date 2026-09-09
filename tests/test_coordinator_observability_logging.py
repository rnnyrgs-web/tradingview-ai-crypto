import continuous_coordinator as coordinator


def test_observability_log_payload_uses_producer_contract_and_is_non_authoritative():
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
                "network_latency_ms": {"p50": 800.0, "p95": 2400.0},
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
                        "research_blocked": False,
                        "research_blocked_reason": None,
                        "untouched_oos_opened": True,
                        "universe_requested": 30,
                        "universe_resolved": 27,
                        "supported_liquidity_subsets": [15, 30],
                        "failed_symbol_count": 2,
                        "failure_type_counts": {"HTTPStatusError": 1, "InsufficientHistory": 1},
                        "selected_oos": {
                            "acc002_research_pass": False,
                            "acc011_survivorship_pass": False,
                            "eligible_for_promotion_review": False,
                            "raw_bootstrap_samples": [1, 2, 3],
                        },
                    },
                },
                "cross-asset-rank-7d": {
                    "last_exit_code": 0,
                    "elapsed_seconds": 3.0,
                    "updated_at_ms": 124,
                    "latest_evidence": {
                        "research_blocked": True,
                        "research_blocked_reason": "insufficient_supported_liquidity_subsets",
                        "untouched_oos_opened": False,
                        "universe_requested": 30,
                        "universe_resolved": 18,
                        "supported_liquidity_subsets": [15],
                        "failed_symbol_count": 2,
                        "failure_type_counts": {"InsufficientHistory": 2},
                        "selected_oos": None,
                    },
                },
            },
        }
    }

    payload = coordinator.observability_log_payload(army)
    assert payload["network_p50_ms"] == 800.0
    assert payload["network_p95_ms"] == 2400.0
    assert payload["acc002_24h"]["elapsed_s"] == 42.5
    assert payload["acc002_24h"]["research_blocked"] is False
    assert payload["acc002_24h"]["untouched_oos_opened"] is True
    assert payload["acc002_24h"]["acc002_pass"] is False
    assert payload["acc002_24h"]["survivorship_pass"] is False
    assert payload["acc002_24h"]["promotion_review"] is False
    assert payload["acc002_24h"]["universe_requested"] == 30
    assert payload["acc002_24h"]["universe_resolved"] == 27
    assert payload["acc002_24h"]["supported_liquidity_subsets"] == [15, 30]
    assert payload["acc002_24h"]["minimum_subset_coverage"] == 0.8
    assert payload["acc002_24h"]["failed_symbol_count"] == 2
    assert payload["acc002_24h"]["failure_type_counts"] == {"HTTPStatusError": 1, "InsufficientHistory": 1}
    assert payload["acc002_7d"]["research_blocked"] is True
    assert payload["acc002_7d"]["research_blocked_reason"] == "insufficient_supported_liquidity_subsets"
    assert payload["acc002_7d"]["untouched_oos_opened"] is False
    assert payload["acc002_7d"]["acc002_pass"] is None
    assert payload["acc002_7d"]["universe_resolved"] == 18
    assert payload["acc002_7d"]["supported_liquidity_subsets"] == [15]
    assert payload["acc002_7d"]["minimum_subset_coverage"] == 0.8
    assert payload["acc002_7d"]["failed_symbol_count"] == 2
    assert payload["acc002_7d"]["failure_type_counts"] == {"InsufficientHistory": 2}
    assert "raw_bootstrap_samples" not in str(payload)
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["signal_authority"] is False


def test_observability_log_payload_can_aggregate_sanitized_failure_types():
    army = {
        "observability": {
            "acc002": {
                "cross-asset-rank-24h": {
                    "latest_evidence": {
                        "supported_liquidity_subsets": [15],
                        "failed_symbols": [
                            {"error_type": "InsufficientHistory"},
                            {"error_type": "HTTPStatusError"},
                            {"error_type": "InsufficientHistory"},
                        ],
                    }
                }
            }
        }
    }
    payload = coordinator.observability_log_payload(army)
    assert payload["acc002_24h"]["failed_symbol_count"] == 3
    assert payload["acc002_24h"]["failure_type_counts"] == {
        "HTTPStatusError": 1,
        "InsufficientHistory": 2,
    }


def test_observability_log_payload_filters_malformed_producer_failure_counts():
    army = {
        "observability": {
            "acc002": {
                "cross-asset-rank-7d": {
                    "latest_evidence": {
                        "supported_liquidity_subsets": [15],
                        "failed_symbol_count": 4,
                        "failure_type_counts": {
                            "InsufficientHistory": 3,
                            "": 1,
                            "HTTPStatusError": -1,
                            "TimeoutError": True,
                            "ConnectError": "1",
                        },
                    }
                }
            }
        }
    }
    payload = coordinator.observability_log_payload(army)
    assert payload["acc002_7d"]["failed_symbol_count"] == 4
    assert payload["acc002_7d"]["failure_type_counts"] == {"InsufficientHistory": 3}


def test_observability_log_payload_handles_missing_state():
    payload = coordinator.observability_log_payload(None)
    assert payload["network_p50_ms"] is None
    assert payload["worker_completed"] is None
    assert payload["acc002_24h"]["research_blocked"] is None
    assert payload["acc002_24h"]["promotion_review"] is None
    assert payload["acc002_24h"]["universe_resolved"] is None
    assert payload["acc002_24h"]["supported_liquidity_subsets"] is None
    assert payload["acc002_24h"]["minimum_subset_coverage"] is None
    assert payload["acc002_24h"]["failed_symbol_count"] == 0
    assert payload["acc002_24h"]["failure_type_counts"] == {}
    assert payload["trade_authority"] is False

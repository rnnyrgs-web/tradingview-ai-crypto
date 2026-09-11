import httpx

import continuous_coordinator
import ffrizz_secondary_runner
import market_data


def _status_error(code):
    request = httpx.Request("GET", "https://example.invalid/futures/data/openInterestHist")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("synthetic", request=request, response=response)


def test_market_data_buckets_synthetic_http_statuses():
    assert market_data._http_status_bucket(_status_error(451)) == "http_451"
    assert market_data._http_status_bucket(_status_error(429)) == "http_429"
    assert market_data._http_status_bucket(_status_error(418)) == "http_other_4xx"
    assert market_data._http_status_bucket(_status_error(503)) == "http_5xx"


def test_ffrizz_runner_preserves_http_status_bucket(monkeypatch):
    monkeypatch.setattr(
        ffrizz_secondary_runner,
        "get_derivatives_history",
        lambda base, limit=90: {
            "open_interest_history": {"binance": []},
            "errors": [{
                "source": "binance_open_interest_history",
                "error_type": "HTTPStatusError",
                "http_status_bucket": "http_451",
            }],
        },
    )
    result = ffrizz_secondary_runner._oi_points("BTC")
    assert result == []
    assert result.source_status == "http_451"


def test_coordinator_preserves_bounded_http_status_counts():
    army = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "oi_source_diagnostics": {
                            "diagnostic_only": True,
                            "acquisition_attempts": 12,
                            "status_counts": {
                                "http_451": 7,
                                "http_429": 2,
                                "http_other_4xx": 1,
                                "http_5xx": 2,
                            },
                        },
                    },
                },
            },
        },
        "supervisor": {"healthy": True},
    }
    payload = continuous_coordinator.observability_log_payload(army)
    oi = payload["ffrizz_forward"]["oi_source_diagnostics"]
    assert oi["acquisition_attempts"] == 12
    assert oi["status_counts"] == {
        "http_451": 7,
        "http_429": 2,
        "http_other_4xx": 1,
        "http_5xx": 2,
    }
    assert oi["symbol_level_data_exposed"] is False
    assert oi["trade_authority"] is False
    assert oi["promotion_authority"] is False

import ffrizz_secondary_runner as ffrizz
from research_adaptive_accuracy_runner import _bounded_oi_source_diagnostics


def test_ffrizz_preserves_allowlisted_http_status_bucket(monkeypatch):
    def fake_derivatives_history(base, limit=90):
        assert limit == 90
        return {
            "open_interest_history": {"binance": []},
            "errors": [
                {
                    "source": "binance_open_interest_history",
                    "error_type": "HTTPStatusError",
                    "http_status_bucket": "http_451",
                    "symbol": "SHOULD_NOT_ESCAPE",
                    "url": "https://example.invalid/private-detail",
                }
            ],
        }

    monkeypatch.setattr(ffrizz, "get_derivatives_history", fake_derivatives_history)
    points = ffrizz._oi_points("BTC")

    assert list(points) == []
    assert points.source_status == "http_451"


def test_ffrizz_falls_back_when_http_bucket_is_not_allowlisted(monkeypatch):
    monkeypatch.setattr(
        ffrizz,
        "get_derivatives_history",
        lambda base, limit=90: {
            "open_interest_history": {"binance": []},
            "errors": [
                {
                    "source": "binance_open_interest_history",
                    "error_type": "HTTPStatusError",
                    "http_status_bucket": "http_418_unapproved",
                }
            ],
        },
    )

    points = ffrizz._oi_points("BTC")
    assert points.source_status == "http_error"


def test_final_boundary_keeps_only_allowlisted_aggregate_http_buckets():
    bounded = _bounded_oi_source_diagnostics(
        {
            "diagnostic_only": True,
            "source": "binance_open_interest_history",
            "acquisition_attempts": 12,
            "status_counts": {
                "http_451": 7,
                "http_429": 2,
                "http_other_4xx": 1,
                "http_5xx": 1,
                "http_other": 1,
                "http_418_unapproved": 99,
            },
            "symbol": "SHOULD_NOT_ESCAPE",
            "url": "https://example.invalid/private-detail",
        }
    )

    assert bounded["acquisition_attempts"] == 12
    assert bounded["status_counts"] == {
        "http_451": 7,
        "http_429": 2,
        "http_other_4xx": 1,
        "http_5xx": 1,
        "http_other": 1,
    }
    rendered = repr(bounded)
    assert "SHOULD_NOT_ESCAPE" not in rendered
    assert "example.invalid" not in rendered
    assert "http_418_unapproved" not in rendered
    assert bounded["extra_requests_added"] == 0
    assert bounded["trade_authority"] is False
    assert bounded["promotion_authority"] is False

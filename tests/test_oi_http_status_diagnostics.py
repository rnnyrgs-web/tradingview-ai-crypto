import httpx

import market_data


def _http_error(status):
    request = httpx.Request("GET", "https://example.invalid")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("bounded upstream failure", request=request, response=response)


def test_http_status_bucket_is_fixed_and_non_sensitive():
    assert market_data._http_status_bucket(_http_error(451)) == "http_451"
    assert market_data._http_status_bucket(_http_error(429)) == "http_429"
    assert market_data._http_status_bucket(_http_error(418)) == "http_other_4xx"
    assert market_data._http_status_bucket(_http_error(503)) == "http_5xx"
    assert market_data._http_status_bucket(_http_error(302)) == "http_other"
    assert market_data._http_status_bucket(RuntimeError("secret")) is None


def test_derivatives_history_records_bounded_oi_http_status_without_retry(monkeypatch):
    calls = []

    def fake_okx(path, params=None):
        if path in {
            "/api/v5/public/funding-rate-history",
            "/api/v5/market/history-mark-price-candles",
            "/api/v5/market/history-index-candles",
        }:
            return []
        raise AssertionError(path)

    def fake_binance(_base, path, params=None):
        calls.append(path)
        if path == "/fapi/v1/fundingRate":
            return []
        if path == "/futures/data/openInterestHist":
            raise _http_error(451)
        raise AssertionError(path)

    monkeypatch.setattr(market_data, "okx_get", fake_okx)
    monkeypatch.setattr(market_data, "_binance_get", fake_binance)

    result = market_data.get_derivatives_history("BTC")
    oi_errors = [
        error
        for error in result["errors"]
        if error.get("source") == "binance_open_interest_history"
    ]

    assert oi_errors == [
        {
            "source": "binance_open_interest_history",
            "error_type": "HTTPStatusError",
            "http_status_bucket": "http_451",
        }
    ]
    assert calls.count("/futures/data/openInterestHist") == 1
    assert "BTC" not in repr(oi_errors)
    assert "example.invalid" not in repr(oi_errors)

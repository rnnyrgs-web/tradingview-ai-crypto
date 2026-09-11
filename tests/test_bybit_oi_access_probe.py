import httpx

from bybit_oi_access_probe import probe


FORBIDDEN_KEYS = {"symbol", "url", "endpoint", "payload", "response", "error", "params"}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_probe_accepts_structurally_valid_public_oi_history_once():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "list": [
                        {"openInterest": "123.45", "timestamp": "1700000000000"},
                        {"openInterest": "124.00", "timestamp": "1700003600000"},
                    ]
                },
            },
            request=request,
        )

    with _client(handler) as client:
        result = probe(client=client)

    assert len(calls) == 1
    assert result["status"] == "available"
    assert result["points_observed"] == 2
    assert result["requests_attempted"] == 1
    assert result["venue_substitution"] is False
    assert result["used_for_signal_scoring"] is False
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert FORBIDDEN_KEYS.isdisjoint(result)


def test_probe_classifies_geographic_http_block_without_leaking_details():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(451, text="restricted", request=request)

    with _client(handler) as client:
        result = probe(client=client)

    assert len(calls) == 1
    assert result["status"] == "http_451"
    assert result["points_observed"] == 0
    assert FORBIDDEN_KEYS.isdisjoint(result)


def test_probe_distinguishes_common_4xx_without_leaking_response_details():
    for status_code, expected in ((400, "http_400"), (401, "http_401"), (403, "http_403"), (404, "http_404"), (429, "http_429")):
        def handler(request, status_code=status_code):
            return httpx.Response(status_code, text="sensitive upstream detail", request=request)

        with _client(handler) as client:
            result = probe(client=client)

        assert result["status"] == expected
        assert result["points_observed"] == 0
        assert result["requests_attempted"] == 1
        assert FORBIDDEN_KEYS.isdisjoint(result)
        assert result["used_for_signal_scoring"] is False
        assert result["trade_authority"] is False


def test_probe_fails_closed_on_application_error_or_malformed_rows():
    def app_error(request):
        return httpx.Response(200, json={"retCode": 10001, "retMsg": "bad"}, request=request)

    with _client(app_error) as client:
        result = probe(client=client)
    assert result["status"] == "invalid_payload"
    assert result["used_for_signal_scoring"] is False

    def malformed(request):
        return httpx.Response(
            200,
            json={"retCode": 0, "result": {"list": [{"openInterest": "x", "timestamp": "bad"}]}},
            request=request,
        )

    with _client(malformed) as client:
        result = probe(client=client)
    assert result["status"] == "invalid_payload"
    assert result["trade_authority"] is False


def test_probe_distinguishes_valid_empty_from_invalid_payload():
    def empty(request):
        return httpx.Response(200, json={"retCode": 0, "result": {"list": []}}, request=request)

    with _client(empty) as client:
        result = probe(client=client)

    assert result["status"] == "valid_empty"
    assert result["points_observed"] == 0
    assert result["persistence_authority"] is False
    assert result["broker_authority"] is False

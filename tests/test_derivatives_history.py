import market_data


def test_normalized_history_points_sorts_dedupes_and_rejects_invalid_rows():
    rows = [
        {"ts": "3000", "v": "3.0"},
        {"ts": "1000", "v": "1.0"},
        {"ts": "2000", "v": "2.0"},
        {"ts": "2000", "v": "2.5"},
        {"ts": "bad", "v": "9"},
        {"ts": "4000", "v": None},
    ]
    assert market_data._normalized_history_points(rows, "ts", "v") == [
        {"ts": 1000, "value": 1.0},
        {"ts": 2000, "value": 2.5},
        {"ts": 3000, "value": 3.0},
    ]


def test_derivatives_history_collects_two_funding_sources_and_oi_change(monkeypatch):
    def fake_okx(path, params=None):
        assert path == "/api/v5/public/funding-rate-history"
        return [
            {"fundingTime": "3000", "realizedRate": "0.0003"},
            {"fundingTime": "1000", "realizedRate": "0.0001"},
            {"fundingTime": "2000", "realizedRate": "0.0002"},
        ]

    def fake_binance(_base, path, params=None):
        if path == "/fapi/v1/fundingRate":
            return [
                {"fundingTime": 1000, "fundingRate": "0.0001"},
                {"fundingTime": 2000, "fundingRate": "0.0002"},
            ]
        if path == "/futures/data/openInterestHist":
            assert params["period"] == "1h"
            return [
                {"timestamp": 1000, "sumOpenInterestValue": "100"},
                {"timestamp": 2000, "sumOpenInterestValue": "125"},
            ]
        raise AssertionError(path)

    monkeypatch.setattr(market_data, "okx_get", fake_okx)
    monkeypatch.setattr(market_data, "_binance_get", fake_binance)
    result = market_data.get_derivatives_history("btc", limit=20)

    assert result["research_only"] is True
    assert result["base"] == "BTC"
    assert result["funding_source_count"] == 2
    assert result["funding_reliable"] is True
    assert result["funding_history"]["okx"][0]["ts"] == 1000
    assert result["open_interest_change_pct"] == 25.0
    assert result["basis_history"]["available"] is False
    assert result["liquidation_history"]["available"] is False
    assert result["errors"] == []


def test_derivatives_history_fails_closed_on_missing_sources(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(market_data, "okx_get", fail)
    monkeypatch.setattr(market_data, "_binance_get", fail)
    result = market_data.get_derivatives_history("ETH")

    assert result["research_only"] is True
    assert result["funding_reliable"] is False
    assert result["funding_source_count"] == 0
    assert result["open_interest_change_pct"] is None
    assert len(result["errors"]) == 3
    assert {e["error_type"] for e in result["errors"]} == {"RuntimeError"}

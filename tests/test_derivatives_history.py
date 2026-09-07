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


def test_aligned_basis_history_uses_exact_shared_timestamps_only():
    mark = [{"ts": 1000, "value": 101.0}, {"ts": 2000, "value": 102.0}, {"ts": 3000, "value": 103.0}]
    index = [{"ts": 1000, "value": 100.0}, {"ts": 2500, "value": 100.0}, {"ts": 3000, "value": 100.0}]
    result = market_data._aligned_basis_history(mark, index)
    assert [p["ts"] for p in result] == [1000, 3000]
    assert round(result[0]["basis_bps"], 8) == 100.0
    assert round(result[1]["basis_bps"], 8) == 300.0


def test_derivatives_history_collects_two_funding_sources_oi_and_basis(monkeypatch):
    def fake_okx(path, params=None):
        if path == "/api/v5/public/funding-rate-history":
            return [
                {"fundingTime": "3000", "realizedRate": "0.0003"},
                {"fundingTime": "1000", "realizedRate": "0.0001"},
                {"fundingTime": "2000", "realizedRate": "0.0002"},
            ]
        if path == "/api/v5/market/history-mark-price-candles":
            assert params["instId"] == "BTC-USDT-SWAP"
            return [
                [3000, "102", "102", "102", "102", "1"],
                [2000, "101", "101", "101", "101", "1"],
                [1000, "100.5", "100.5", "100.5", "100.5", "1"],
            ]
        if path == "/api/v5/market/history-index-candles":
            assert params["instId"] == "BTC-USDT"
            return [
                [3000, "100", "100", "100", "100", "1"],
                [2000, "100", "100", "100", "100", "1"],
                [1000, "100", "100", "100", "100", "1"],
            ]
        raise AssertionError(path)

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
    assert result["basis_history"]["available"] is True
    assert result["basis_history"]["source"] == "okx_mark_vs_index"
    assert len(result["basis_history"]["points"]) == 3
    assert round(result["basis_history"]["points"][0]["basis_bps"], 8) == 50.0
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
    assert result["basis_history"]["available"] is False
    assert result["basis_history"]["points"] == []
    assert len(result["errors"]) == 5
    assert {e["error_type"] for e in result["errors"]} == {"RuntimeError"}

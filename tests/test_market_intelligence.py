from market_intelligence import derivatives_summary, price_consensus


NOW = 2_000_000


def test_price_consensus_accepts_fresh_close_independent_quotes():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 100.2, "observed_ms": NOW - 1_000},
    ], now_ms=NOW, max_deviation_bps=50)
    assert result["reliable"] is True
    assert result["source_count"] == 2
    assert result["reason"] == "ok"


def test_price_consensus_rejects_exchange_disagreement():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 102.0, "observed_ms": NOW},
    ], now_ms=NOW, max_deviation_bps=50)
    assert result["reliable"] is False
    assert result["reason"] == "exchange_price_disagreement"


def test_price_consensus_rejects_stale_source_and_fails_closed():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 100.0, "observed_ms": NOW - 121_000},
    ], now_ms=NOW, max_age_seconds=120)
    assert result["reliable"] is False
    assert result["reason"] == "insufficient_sources"
    assert result["rejected"] == [{"exchange": "binance", "reason": "stale_quote"}]


def test_derivatives_summary_requires_two_funding_sources_and_flags_crowding():
    result = derivatives_summary([
        {"exchange": "okx", "funding_rate": "0.0006", "open_interest_base": 10},
        {"exchange": "binance", "funding_rate": "0.0008", "open_interest_base": 20},
    ], [{"side": "sell", "price": 100, "size": 3}])
    assert result["reliable"] is True
    assert result["crowding"] == "EXTREME_LONG"
    assert result["median_funding_rate"] == 0.0007
    assert result["liquidations"]["sell_pressure_units"] == 300


def test_derivatives_summary_does_not_claim_reliability_from_one_exchange():
    result = derivatives_summary([
        {"exchange": "okx", "funding_rate": "0.0001", "open_interest_base": 10},
    ])
    assert result["reliable"] is False
    assert result["funding_source_count"] == 1

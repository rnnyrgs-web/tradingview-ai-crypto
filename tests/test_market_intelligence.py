from market_intelligence import cross_exchange_order_book, derivatives_summary, order_book_summary, price_consensus


NOW = 2_000_000


def test_price_consensus_accepts_fresh_close_independent_quotes():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 100.2, "observed_ms": NOW - 1_000},
    ], now_ms=NOW, max_deviation_bps=50)
    assert result["reliable"] is True
    assert result["source_count"] == 2
    assert result["reason"] == "ok"
    assert result["confidence_multiplier"] == 1.0
    assert result["provenance"]["accepted_exchange_names"] == ["binance", "okx"]


def test_price_consensus_rejects_exchange_disagreement():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 102.0, "observed_ms": NOW},
    ], now_ms=NOW, max_deviation_bps=50)
    assert result["reliable"] is False
    assert result["reason"] == "exchange_price_disagreement"
    assert result["confidence_multiplier"] == 0.0


def test_price_consensus_rejects_stale_source_and_fails_closed():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW},
        {"exchange": "binance", "price": 100.0, "observed_ms": NOW - 121_000},
    ], now_ms=NOW, max_age_seconds=120)
    assert result["reliable"] is False
    assert result["reason"] == "insufficient_independent_sources"
    assert result["source_count"] == 1
    assert result["confidence_multiplier"] <= 0.5
    assert result["rejected"][0]["exchange"] == "binance"
    assert result["rejected"][0]["reason"] == "stale_quote"


def test_duplicate_exchange_quotes_cannot_fake_independent_confirmation():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0, "observed_ms": NOW - 1_000},
        {"exchange": "okx", "price": 100.1, "observed_ms": NOW},
    ], now_ms=NOW)
    assert result["reliable"] is False
    assert result["source_count"] == 1
    assert result["provenance"]["raw_observation_count"] == 2
    assert result["provenance"]["independent_source_count"] == 1
    assert any(row["reason"] == "superseded_duplicate_quote" for row in result["rejected"])


def test_missing_timestamp_is_not_treated_as_fresh():
    result = price_consensus([
        {"exchange": "okx", "price": 100.0},
        {"exchange": "binance", "price": 100.0, "observed_ms": NOW},
    ], now_ms=NOW)
    assert result["reliable"] is False
    assert result["source_count"] == 1
    assert any(row["reason"] == "missing_timestamp" for row in result["rejected"])


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


def test_order_book_summary_computes_depth_and_imbalance():
    bids = [[100 - i * 0.01, 2] for i in range(12)]
    asks = [[100.1 + i * 0.01, 1] for i in range(12)]
    result = order_book_summary(bids, asks, min_levels=10, max_spread_bps=20)
    assert result["reliable"] is True
    assert result["imbalance_25bps"] > 0
    assert result["bid_depth_25bps"] > result["ask_depth_25bps"]


def test_order_book_summary_rejects_crossed_and_thin_books():
    crossed = order_book_summary([[101, 1]] * 10, [[100, 1]] * 10, min_levels=10)
    thin = order_book_summary([[99, 1]], [[101, 1]], min_levels=10)
    assert crossed["reliable"] is False
    assert crossed["reason"] == "crossed_book"
    assert thin["reason"] == "insufficient_levels"


def test_cross_exchange_order_book_is_research_only_and_needs_two_sources():
    one = cross_exchange_order_book([{"exchange":"okx","reliable":True,"imbalance_25bps":0.2}])
    two = cross_exchange_order_book([
        {"exchange":"okx","reliable":True,"imbalance_25bps":0.2},
        {"exchange":"binance","reliable":True,"imbalance_25bps":-0.1},
    ])
    assert one["reliable"] is False
    assert two["reliable"] is True
    assert two["research_only"] is True
    assert two["direction_disagreement"] is True

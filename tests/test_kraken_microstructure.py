from kraken_microstructure import summarize_kraken_microstructure


NOW = 2_000_000_000_000


def _book():
    return {
        "observed_ms": NOW - 1_000,
        "bids": [[99.0, 8.0], [98.5, 6.0], [98.0, 4.0]],
        "asks": [[101.0, 2.0], [101.5, 3.0], [102.0, 4.0]],
    }


def test_summary_exposes_timestamp_safe_research_only_microstructure():
    result = summarize_kraken_microstructure("BTC/USD", _book(), now_ms=NOW, depth_levels=2)

    assert result["available"] is True
    assert result["reliable"] is True
    assert result["research_only"] is True
    assert result["historical"] is False
    assert result["broker_connected"] is False
    assert result["order_authority"] is False
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["hidden_liquidity_assumed"] is False
    assert result["spread_bps"] > 0
    assert result["depth_imbalance"] > 0
    assert result["top_level_imbalance"] > 0
    assert result["microprice_deviation_bps"] > 0
    assert result["bid_levels_used"] == 2
    assert result["ask_levels_used"] == 2
    assert -1.0 <= result["depth_imbalance"] <= 1.0
    assert -1.0 <= result["top_level_imbalance"] <= 1.0


def test_summary_fails_closed_for_stale_future_crossed_or_one_sided_books():
    stale = _book()
    stale["observed_ms"] = NOW - 20_000
    assert summarize_kraken_microstructure("BTC/USD", stale, now_ms=NOW)["reason"] == "stale_public_book"

    future = _book()
    future["observed_ms"] = NOW + 6_000
    assert summarize_kraken_microstructure("BTC/USD", future, now_ms=NOW)["reason"] == "future_book_timestamp"

    crossed = _book()
    crossed["bids"] = [[102.0, 1.0]]
    crossed["asks"] = [[101.0, 1.0]]
    assert summarize_kraken_microstructure("BTC/USD", crossed, now_ms=NOW)["reason"] == "crossed_public_book"

    one_sided = _book()
    one_sided["asks"] = []
    assert summarize_kraken_microstructure("BTC/USD", one_sided, now_ms=NOW)["reason"] == "one_sided_or_empty_public_book"


def test_summary_rejects_invalid_policy_and_depth_without_repairing_data():
    assert summarize_kraken_microstructure("", _book(), now_ms=NOW)["reason"] == "invalid_pair"
    assert summarize_kraken_microstructure("BTC/USD", {}, now_ms=NOW)["reason"] == "missing_book_timestamp"
    assert summarize_kraken_microstructure("BTC/USD", _book(), now_ms=NOW, max_age_seconds=-1)["reason"] == "invalid_age_policy"
    assert summarize_kraken_microstructure("BTC/USD", _book(), now_ms=NOW, depth_levels=0)["reason"] == "invalid_depth_levels"
    assert summarize_kraken_microstructure("BTC/USD", _book(), now_ms=NOW, depth_levels=101)["reason"] == "invalid_depth_levels"

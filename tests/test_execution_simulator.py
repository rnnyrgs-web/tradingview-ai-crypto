from execution_simulator import simulate_market_fill


def _exchange(vwap_buy=100.1, vwap_sell=99.9, slip=10.0, complete=True):
    return {
        "reliable": True,
        "live_fill_slippage": {
            "available": True,
            "historical": False,
            "estimates": [
                {
                    "quote_notional": 1000.0,
                    "buy": {"complete_fill": complete, "vwap": vwap_buy, "slippage_bps_vs_mid": slip},
                    "sell": {"complete_fill": complete, "vwap": vwap_sell, "slippage_bps_vs_mid": slip},
                },
                {
                    "quote_notional": 5000.0,
                    "buy": {"complete_fill": complete, "vwap": vwap_buy + 0.1, "slippage_bps_vs_mid": slip + 5},
                    "sell": {"complete_fill": complete, "vwap": vwap_sell - 0.1, "slippage_bps_vs_mid": slip + 5},
                },
                {
                    "quote_notional": 10000.0,
                    "buy": {"complete_fill": complete, "vwap": vwap_buy + 0.2, "slippage_bps_vs_mid": slip + 10},
                    "sell": {"complete_fill": complete, "vwap": vwap_sell - 0.2, "slippage_bps_vs_mid": slip + 10},
                },
            ],
        },
    }


def _book():
    return {"reliable": True, "exchanges": [_exchange(), _exchange(100.15, 99.85, 12.0)]}


def test_uses_smallest_supported_tier_above_requested_size():
    result = simulate_market_fill(_book(), "LONG", 4000.0, fee_bps=6.0)
    assert result.executable
    assert result.supported_notional == 5000.0
    assert result.source_count == 2
    assert result.fill_price > 100.25


def test_uses_worst_independent_execution_not_best():
    result = simulate_market_fill(_book(), "LONG", 1000.0)
    assert result.executable
    assert result.fill_price == 100.15


def test_short_fill_is_adversely_reduced_by_fee():
    no_fee = simulate_market_fill(_book(), "SHORT", 1000.0, fee_bps=0.0)
    fee = simulate_market_fill(_book(), "SHORT", 1000.0, fee_bps=6.0)
    assert fee.executable
    assert fee.fill_price < no_fee.fill_price


def test_does_not_extrapolate_beyond_visible_supported_notional():
    result = simulate_market_fill(_book(), "LONG", 12000.0)
    assert not result.executable
    assert result.reason == "insufficient_independent_visible_depth"


def test_requires_two_reliable_exchange_sources():
    book = {"reliable": True, "exchanges": [_exchange()]}
    result = simulate_market_fill(book, "LONG", 1000.0)
    assert not result.executable


def test_incomplete_fills_are_not_treated_as_liquidity():
    book = {"reliable": True, "exchanges": [_exchange(complete=False), _exchange(complete=False)]}
    result = simulate_market_fill(book, "LONG", 1000.0)
    assert not result.executable


def test_unreliable_book_and_malformed_requests_fail_closed():
    assert not simulate_market_fill({"reliable": False}, "LONG", 1000).executable
    assert not simulate_market_fill(_book(), "BAD", 1000).executable
    assert not simulate_market_fill(_book(), "LONG", float("nan")).executable

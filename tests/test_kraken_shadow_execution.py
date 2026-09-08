from kraken_shadow_execution import shadow_market_fill


NOW = 2_000_000_000_000


def _book():
    return {
        "observed_ms": NOW - 1_000,
        "asks": [[100.0, 5.0], [101.0, 10.0]],
        "bids": [[99.0, 5.0], [98.0, 10.0]],
    }


def test_long_shadow_fill_walks_visible_asks_and_applies_fee():
    fill = shadow_market_fill("BTC/USD", "LONG", 1000.0, _book(), fee_bps=20, now_ms=NOW)
    assert fill.executable is True
    assert fill.shadow_only is True
    assert fill.broker_connected is False
    assert fill.order_authority is False
    assert fill.trade_authority is False
    assert fill.vwap > 100.0
    assert fill.after_fee_fill_price > fill.vwap
    assert fill.slippage_bps > 0


def test_short_shadow_fill_walks_visible_bids_conservatively():
    fill = shadow_market_fill("BTC/USD", "SHORT", 1000.0, _book(), fee_bps=20, now_ms=NOW)
    assert fill.executable is True
    assert fill.vwap < 99.0
    assert fill.after_fee_fill_price < fill.vwap
    assert fill.slippage_bps > 0


def test_insufficient_visible_depth_fails_closed_without_extrapolation():
    fill = shadow_market_fill("BTC/USD", "LONG", 10_000.0, _book(), now_ms=NOW)
    assert fill.executable is False
    assert fill.reason == "insufficient_visible_kraken_depth"


def test_stale_missing_and_future_books_fail_closed():
    stale = _book()
    stale["observed_ms"] = NOW - 20_000
    assert shadow_market_fill("BTC/USD", "LONG", 100.0, stale, now_ms=NOW).reason == "stale_public_book"
    assert shadow_market_fill("BTC/USD", "LONG", 100.0, {}, now_ms=NOW).reason == "missing_book_timestamp"
    future = _book()
    future["observed_ms"] = NOW + 6_000
    assert shadow_market_fill("BTC/USD", "LONG", 100.0, future, now_ms=NOW).reason == "future_book_timestamp"


def test_invalid_request_and_fee_fail_closed():
    assert shadow_market_fill("BTC/USD", "WAIT", 100.0, _book(), now_ms=NOW).reason == "invalid_request"
    assert shadow_market_fill("BTC/USD", "LONG", -1.0, _book(), now_ms=NOW).reason == "invalid_request"
    assert shadow_market_fill("BTC/USD", "LONG", 100.0, _book(), fee_bps=-1, now_ms=NOW).reason == "invalid_fee"

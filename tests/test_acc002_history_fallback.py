from types import SimpleNamespace

import acc002_history_fallback as fallback
import cross_asset_runner as runner


def _kline(ts, close=100.0):
    return [str(ts), str(close), str(close + 1), str(close - 1), str(close), "10", "1000"]


def _history(count, step=4 * 60 * 60 * 1000, start=1_700_000_000_000):
    return [
        {
            "ts": start + i * step,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 10.0,
            "quote_volume": 1000.0,
        }
        for i in range(count)
    ]


def test_bybit_symbol_requires_exact_usdt_spot_symbol():
    assert fallback._bybit_symbol("BTC-USDT") == "BTCUSDT"
    for invalid in ("BTC-USD", "BTC-USDT-SWAP", "", "BTC"):
        try:
            fallback._bybit_symbol(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {invalid!r}")


def test_normalize_drops_open_candle_and_requires_strict_completed_data():
    step = 4 * 60 * 60 * 1000
    now_ms = 1_700_100_000_000
    completed = now_ms - 2 * step
    still_open = now_ms - step // 2
    rows = fallback._normalize(
        [_kline(completed), _kline(still_open)],
        interval_ms=step,
        now_ms=now_ms,
    )
    assert [row["ts"] for row in rows] == [completed]


def test_strict_complete_window_rejects_gap_and_never_stitches():
    step = 4 * 60 * 60 * 1000
    rows = _history(5, step=step)
    assert len(fallback._strict_complete_window(rows, wanted=5, interval_ms=step)) == 5
    rows[3] = {**rows[3], "ts": rows[3]["ts"] + step}
    assert fallback._strict_complete_window(rows, wanted=5, interval_ms=step) == []


def test_recovery_uses_exact_missing_ranked_assets_and_stops_when_two_subsets_supported(monkeypatch):
    symbols = [f"C{i}-USDT" for i in range(30)]
    histories = {symbol: _history(20) for symbol in symbols[:20]}
    primary_shortfalls = {
        symbol: {
            "symbol": symbol,
            "error_type": "InsufficientHistory",
            "bars_received": 100,
            "bars_required": 20,
        }
        for symbol in symbols[20:]
    }
    calls = []

    def fake_bybit(symbol, *, bar, bars):
        calls.append(symbol)
        return _history(bars)

    monkeypatch.setattr(runner, "get_complete_bybit_spot_history", fake_bybit)
    rescued, failures, provenance = runner._recover_7d_history_deficit(
        symbols=symbols,
        histories=dict(histories),
        primary_shortfalls=primary_shortfalls,
        bar="4H",
        bars=20,
        minimum_bars=20,
    )

    assert calls == symbols[20:24]
    assert all(symbol in rescued for symbol in symbols[:24])
    assert len(rescued) == 24
    assert runner._build_liquidity_subsets(symbols, rescued).keys() == {15, 30}
    assert provenance["fallback_attempts"] == 4
    assert provenance["fallback_rescued_assets"] == 4
    assert provenance["no_venue_stitching"] is True
    assert provenance["no_rank_substitution"] is True
    assert {item["symbol"] for item in failures} == set(symbols[24:])


def test_recovery_keeps_primary_failure_when_bybit_history_is_partial(monkeypatch):
    symbols = [f"C{i}-USDT" for i in range(30)]
    histories = {symbol: _history(20) for symbol in symbols[:20]}
    primary_shortfalls = {
        symbol: {"symbol": symbol, "error_type": "InsufficientHistory", "bars_required": 20}
        for symbol in symbols[20:]
    }
    monkeypatch.setattr(
        runner,
        "get_complete_bybit_spot_history",
        lambda symbol, *, bar, bars: _history(19),
    )

    rescued, failures, provenance = runner._recover_7d_history_deficit(
        symbols=symbols,
        histories=dict(histories),
        primary_shortfalls=primary_shortfalls,
        bar="4H",
        bars=20,
        minimum_bars=20,
    )

    assert len(rescued) == 20
    assert provenance["fallback_attempts"] == 10
    assert provenance["fallback_rescued_assets"] == 0
    assert provenance["fallback_failed_assets"] == 10
    assert all(item["fallback_error_type"] == "InsufficientBybitHistory" for item in failures)

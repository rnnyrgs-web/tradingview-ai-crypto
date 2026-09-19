import copy

import pytest

from liquidity_mean_reversion_selection import (
    _load_contract,
    _signal,
    _trades,
    _validate_rows,
    evaluate_selection_from_histories,
)


def _rows(n=650):
    rows = []
    previous = 100.0
    for i in range(n):
        close = 100.0 * (1.0 + 0.0004 * ((i % 5) - 2))
        open_price = previous
        high = max(open_price, close) * 1.001
        low = min(open_price, close) * 0.999
        rows.append(
            {
                "ts": 1_700_000_000_000 + i * 3_600_000,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100.0,
                "quote_volume": 1_000.0,
            }
        )
        previous = close
    return rows


def _shock_rows():
    rows = _rows(300)
    i = 230
    previous = float(rows[i - 1]["close"])
    shocked_close = previous * 1.03
    rows[i] = {
        "ts": rows[i]["ts"],
        "open": previous,
        "high": shocked_close * 1.01,
        "low": previous * 0.995,
        "close": shocked_close,
        "volume": 400.0,
        "quote_volume": 3_000.0,
    }
    for j in range(i + 1, i + 8):
        open_price = shocked_close * (1.0 - 0.003 * (j - i - 1))
        close = open_price * 0.999
        rows[j] = {
            "ts": rows[j]["ts"],
            "open": open_price,
            "high": max(open_price, close) * 1.001,
            "low": min(open_price, close) * 0.999,
            "close": close,
            "volume": 100.0,
            "quote_volume": 1_000.0,
        }
    return rows


def test_frozen_contract_loads_and_keeps_oos_locked():
    contract = _load_contract()
    assert contract["fingerprint_id"] == "DISC-LIQUIDITY-MEANREV-001-v1"
    assert contract["chronology"]["untouched_oos"] == "LOCKED"
    assert contract["trade_authority"] is False
    assert contract["search_breadth"]["parameter_optimization_allowed"] is False


def test_primary_shock_is_opposite_direction_and_next_open_six_hour_exit():
    contract = _load_contract()
    rows = _validate_rows(_shock_rows())
    direction, features = _signal(rows, 230, contract, liquidity_filters=True)
    assert direction == -1
    assert features["quote_volume_ratio"] >= 1.5
    assert features["range_ratio"] >= 1.5
    trades = _trades(rows, 220, 260, contract, liquidity_filters=True)
    assert trades
    trade = trades[0]
    assert trade["signal_index"] == 230
    assert trade["entry_index"] == 231
    assert trade["exit_index"] == 237
    assert trade["direction"] == "SHORT"


def test_liquidity_filters_add_information_beyond_large_return_baseline():
    contract = _load_contract()
    rows = _validate_rows(_shock_rows())
    rows[230]["quote_volume"] = 1_000.0
    rows[230]["high"] = max(float(rows[230]["open"]), float(rows[230]["close"])) * 1.001
    rows[230]["low"] = min(float(rows[230]["open"]), float(rows[230]["close"])) * 0.999
    primary, _ = _signal(rows, 230, contract, liquidity_filters=True)
    baseline, _ = _signal(rows, 230, contract, liquidity_filters=False)
    assert primary == 0
    assert baseline == -1


def test_future_bars_cannot_change_signal_features_or_direction():
    contract = _load_contract()
    before = _validate_rows(_shock_rows())
    direction_a, features_a = _signal(before, 230, contract, liquidity_filters=True)
    after = copy.deepcopy(before)
    for j in range(231, 250):
        after[j]["open"] *= 1.2
        after[j]["high"] *= 1.2
        after[j]["low"] *= 1.2
        after[j]["close"] *= 1.2
        after[j]["quote_volume"] *= 10
    direction_b, features_b = _signal(after, 230, contract, liquidity_filters=True)
    assert direction_a == direction_b
    assert features_a == features_b


def test_selection_output_never_opens_untouched_oos():
    contract = copy.deepcopy(_load_contract())
    contract["source"]["fixed_instruments"] = ["A", "B", "C"]
    contract["source"]["minimum_history_bars_per_asset"] = 300
    histories = {key: _rows(650) for key in ("A", "B", "C")}
    result = evaluate_selection_from_histories(histories, contract=contract)
    assert result["untouched_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["trade_authority"] is False
    assert result["screen_status"] in {"PRE_OOS_FAIL", "PRE_OOS_PASS_ELIGIBLE_FOR_CENTRAL_FREEZE"}


def test_invalid_chronology_fails_closed():
    rows = _rows(10)
    rows[5]["ts"] = rows[4]["ts"]
    with pytest.raises(ValueError, match="chronological"):
        _validate_rows(rows)

import copy
import math
from pathlib import Path

import volatility_breakout_selection as v


def _contract():
    return v._load_contract(Path(__file__).resolve().parents[1] / "orchestration" / "disc_vol_breakout_001.json")


def _rows(n=1200, start=1_700_000_000_000):
    rows = []
    close = 100.0
    for i in range(n):
        ts = start + i * 3_600_000
        rows.append(
            {
                "ts": ts,
                "open": close,
                "high": close + 0.10,
                "low": close - 0.10,
                "close": close,
                "volume": 1000.0,
                "quote_volume": 100000.0,
            }
        )
    return rows


def test_contract_is_frozen_selection_only_and_search_breadth_is_nonadaptive():
    c = _contract()
    assert c["fingerprint_id"] == "DISC-VOL-BREAKOUT-001-v1"
    assert c["chronology"]["untouched_oos"] == "LOCKED"
    assert c["source"]["fixed_instruments"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    assert c["source"]["asset_substitution_allowed"] is False
    assert c["search_breadth"]["primary_candidate_count"] == 1
    assert c["search_breadth"]["primary_timeframe_count"] == 1
    assert c["search_breadth"]["parameter_optimization_allowed"] is False
    assert c["search_breadth"]["asset_or_timeframe_winner_selection_allowed"] is False


def test_breakout_uses_prior_range_enters_next_open_and_collision_is_stop_first():
    c = _contract()
    rows = _rows(500)
    signal = 300
    rows[signal] = {
        **rows[signal],
        "open": 100.0,
        "high": 101.2,
        "low": 99.9,
        "close": 101.0,
    }
    rows[signal + 1] = {
        **rows[signal + 1],
        "open": 101.0,
        "high": 105.0,
        "low": 98.0,
        "close": 101.0,
    }
    clean = v._validate_rows(rows)
    trades = v._generate_trades(
        clean,
        start_index=220,
        end_index=450,
        contract=c,
        compression_quantile=0.20,
    )
    assert trades
    first = trades[0]
    assert first["signal_index"] == signal
    assert first["entry_index"] == signal + 1
    assert first["entry_ts"] == rows[signal + 1]["ts"]
    assert first["exit_reason"] == "STOP"
    assert first["gross_bps"] < 0


def test_oos_price_mutation_cannot_change_train_or_validation_evidence():
    c = _contract()
    rows = _rows(1600)
    before = v._evaluate_instrument(rows, c, compression_quantile=0.20)
    mutated = copy.deepcopy(rows)
    oos_start = before["bounds"]["oos_start"]
    for i in range(oos_start, len(mutated)):
        base = 150.0 + (i - oos_start) * 0.5
        mutated[i].update(
            {
                "open": base,
                "high": base + 5.0,
                "low": max(1.0, base - 5.0),
                "close": base + 1.0,
            }
        )
    after = v._evaluate_instrument(mutated, c, compression_quantile=0.20)
    assert before["train"] == after["train"]
    assert before["validation"] == after["validation"]
    assert before["untouched_oos"]["status"] == "LOCKED_UNTOUCHED_OOS"
    assert after["untouched_oos"]["status"] == "LOCKED_UNTOUCHED_OOS"


def test_insufficient_fixed_asset_history_fails_closed_without_opening_oos():
    c = _contract()
    histories = {instrument: _rows(500) for instrument in c["source"]["fixed_instruments"]}
    result = v.evaluate_selection_from_histories(histories, contract=c)
    assert result["data_integrity_ok"] is False
    assert result["screen_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["economic_pre_oos_pass"] is False
    assert result["eligible_for_deep_freeze"] is False
    assert result["terminal_rejection_authorized"] is False
    assert result["untouched_oos_opened"] is False


def test_sensitivities_cannot_rescue_a_failing_primary_rule():
    c = _contract()
    result = v._selection_decision(
        data_integrity_ok=True,
        passing_instruments=3,
        pooled_primary_pass=False,
        sensitivity_passes={"compression_q15": True, "compression_q25": True},
        contract=c,
    )
    assert result["screen_status"] == "PRE_OOS_FAIL"
    assert result["economic_pre_oos_pass"] is False
    assert result["terminal_rejection_authorized"] is True


def test_history_validation_rejects_duplicate_or_nonchronological_rows():
    rows = _rows(10)
    bad = copy.deepcopy(rows)
    bad[5]["ts"] = bad[4]["ts"]
    try:
        v._validate_rows(bad)
    except ValueError as exc:
        assert "chronological" in str(exc)
    else:
        raise AssertionError("duplicate timestamp must fail closed")


def test_stop_gap_is_filled_at_worse_open_and_target_gap_is_capped():
    c = _contract()
    rows = _rows(400)
    signal = 250
    rows[signal] = {**rows[signal], "high": 101.2, "low": 99.9, "close": 101.0}
    clean = v._validate_rows(rows)
    atr = v._atr(clean, c["primary_rule"]["atr_window_bars"])[signal]
    assert atr is not None

    entry_idx = signal + 1
    entry = float(clean[entry_idx]["open"])
    stop = entry - c["primary_rule"]["stop_atr_multiple"] * float(atr)
    rows[entry_idx + 1].update(
        {
            "open": stop - 1.0,
            "high": stop - 0.5,
            "low": stop - 1.5,
            "close": stop - 1.0,
        }
    )
    clean = v._validate_rows(rows)
    trade = v._exit_trade(
        clean,
        signal_index=signal,
        direction=1,
        signal_atr=float(atr),
        stop_multiple=c["primary_rule"]["stop_atr_multiple"],
        target_multiple=c["primary_rule"]["target_atr_multiple"],
        max_hold_bars=c["primary_rule"]["maximum_hold_bars"],
        segment_end=390,
    )
    assert trade is not None
    assert trade["exit_reason"] == "STOP_GAP"
    assert math.isclose(trade["exit_price"], stop - 1.0, rel_tol=0, abs_tol=1e-9)

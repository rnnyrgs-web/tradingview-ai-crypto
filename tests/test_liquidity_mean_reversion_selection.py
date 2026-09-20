import copy

import pytest

from liquidity_mean_reversion_selection import (
    _load_contract,
    _evaluate,
    _load_frozen_cache,
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
                "ts": 1_699_999_200_000 + i * 3_600_000,
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
    contract = _load_contract()
    histories = {key: _rows(650) for key in contract["source"]["fixed_instruments"]}
    result = evaluate_selection_from_histories(histories, contract=contract)
    assert result["untouched_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["trade_authority"] is False
    assert result["data_integrity_ok"] is False
    assert result["economic_pre_oos_pass"] is False
    assert result["terminal_rejection_authorized"] is False
    assert len(result["data_errors"]) == 3
    assert all("INSUFFICIENT_HISTORY" in value for value in result["data_errors"].values())


def test_invalid_chronology_fails_closed():
    rows = _rows(10)
    rows[5]["ts"] = rows[4]["ts"]
    with pytest.raises(ValueError, match="chronological"):
        _validate_rows(rows)


@pytest.mark.parametrize("rehash", [False, True])
def test_caller_cannot_change_or_resign_frozen_costs(rehash):
    from volatility_breakout_selection import _sha256_hex
    contract = copy.deepcopy(_load_contract())
    contract["costs"]["base_round_trip_bps"] = 0
    if rehash:
        payload = {k: v for k, v in contract.items() if k not in {"contract_sha256", "contract_fingerprint_definition"}}
        contract["contract_sha256"] = _sha256_hex(payload)
    with pytest.raises(RuntimeError, match="fingerprint mismatch"):
        evaluate_selection_from_histories({}, contract=contract)


def test_missing_hour_cannot_turn_six_bars_into_seven_hour_hold():
    rows = _rows()
    del rows[235]
    with pytest.raises(ValueError, match="missing hourly"):
        _validate_rows(rows)


def test_off_grid_timestamps_fail_closed():
    rows = _rows()
    rows[0]["ts"] += 1
    with pytest.raises(ValueError, match="UTC hourly"):
        _validate_rows(rows)


def test_missing_fixed_asset_cannot_select_surviving_winners():
    result = evaluate_selection_from_histories({})
    assert result["eligible_for_deep_freeze"] is False
    assert result["terminal_rejection_authorized"] is False
    assert len(result["data_errors"]) == 3


def test_oos_prices_do_not_change_train_validation_and_labels_stay_inside():
    contract = _load_contract()
    rows = _rows(650)
    rows[:300] = _shock_rows()
    original = _evaluate(rows, contract)
    assert original["train"]["trades"]
    poisoned = copy.deepcopy(rows)
    for row in poisoned[original["bounds"]["oos_start"]:]:
        for key in ("open", "high", "low", "close", "volume", "quote_volume"):
            row[key] *= 1_000_000
    assert _evaluate(poisoned, contract) == original
    trades = _trades(_shock_rows(), 220, 260, contract)
    assert trades
    assert all(t["entry_index"] == t["signal_index"] + 1 and t["exit_index"] < 260 for t in trades)
    assert all(a["exit_index"] < b["signal_index"] for a, b in zip(trades, trades[1:]))
    assert _trades(_shock_rows(), 220, 237, contract) == []


def test_original_cache_has_verified_provenance_and_locked_oos():
    evidence, dataset = _load_frozen_cache()
    assert evidence["payload"]["selection"]["untouched_oos_opened"] is False
    assert set(dataset["histories"]) == set(_load_contract()["source"]["fixed_instruments"])


def test_missing_cache_has_no_network_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        _load_frozen_cache(tmp_path)


def test_terminal_task_handoff_releases_old_lease_without_dispatching_manual_phase_three():
    from datetime import datetime, timezone
    from agents.autonomous_cloud_runner import default_state, load_config, load_coordination, plan_decision
    state = default_state()
    state["active_task"] = {"role": "data-market", "task_id": "COORD-DISC-DATA-002", "phase": "WAITING_CI", "base_main_sha": "a" * 40, "started_at": "2026-09-19T04:00:00Z"}
    decision = plan_decision(load_config(), load_coordination(), state, "a" * 40, datetime(2026, 9, 19, 4, 10, tzinfo=timezone.utc))
    assert decision.run is False
    assert decision.reason == "NO_READY_AUTONOMOUS_TASK"
    assert decision.role is None
    assert decision.task_id is None


def test_frozen_sample_cost_and_sensitivity_gates_cannot_be_bypassed():
    from liquidity_mean_reversion_selection import _instrument_pass, _sensitivity_pass
    contract = _load_contract()
    p = {seg: {"cost_stress": {"3x": {"trades": 50, "mean_net_bps": 10, "profit_factor": 2}}} for seg in ("train", "validation")}
    assert _instrument_pass(p, p, contract)[0] is True
    short = copy.deepcopy(p)
    short["validation"]["cost_stress"]["3x"]["trades"] = 4
    assert "VALIDATION_SAMPLE_FLOOR" in _instrument_pass(short, p, contract)[1]
    losing = copy.deepcopy(p)
    losing["validation"]["cost_stress"]["3x"]["mean_net_bps"] = 0
    assert "VALIDATION_EXPECTANCY" in _instrument_pass(losing, p, contract)[1]
    assert _sensitivity_pass(losing, contract)[0] is False


def test_descriptive_distribution_uses_after_cost_losses_and_additive_drawdown():
    from liquidity_mean_reversion_audit import distribution
    metrics = distribution([{"gross_bps": n} for n in (30, 0, 20)], 20)
    assert metrics["mean_net_bps"] == pytest.approx(-10 / 3)
    assert metrics["max_drawdown_bps_additive"] == 20
    assert metrics["wins"] == metrics["losses"] == metrics["ties"] == 1
    assert metrics["mean_win_bps"] == 10
    assert metrics["mean_loss_bps"] == -20


def test_durable_descriptive_report_is_reproducible_from_original_selection():
    import json
    from pathlib import Path
    from liquidity_mean_reversion_audit import audit
    original = json.loads(Path("orchestration/evidence/disc_liquidity_meanrev_001_audit_20260919.json").read_text())
    assert audit() == original

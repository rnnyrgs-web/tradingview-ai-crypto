import copy
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btc_leadlag_selection import (
    _iso,
    _load_contract,
    _signal,
    _simulate_segment,
    _validate_histories,
    evaluate_selection_from_histories,
    persist_selection,
    run,
)
from profitability_learning.contracts import validate_experiment
from profitability_learning.memory import Memory
from profitability_learning.runtime import apply_queue_feedback
from research_artifact import verify_research_envelope


def _histories(n=520, impulse=230):
    start = 1_700_002_800_000
    assets = {"BTC-USDT-SWAP": 100.0, "ETH-USDT-SWAP": 50.0, "SOL-USDT-SWAP": 25.0}
    histories = {}
    for asset, base in assets.items():
        rows = []
        previous = base
        for i in range(n):
            close = previous * (1 + (0.0002 if i % 2 else -0.0002))
            if i == impulse:
                close = previous * (1.03 if asset == "BTC-USDT-SWAP" else 1.005)
            if impulse < i <= impulse + 7 and asset != "BTC-USDT-SWAP":
                close = previous * 1.004
            rows.append({
                "ts": start + i * 3_600_000,
                "open": previous,
                "high": max(previous, close) * 1.001,
                "low": min(previous, close) * 0.999,
                "close": close,
                "volume": 100.0,
                "quote_volume": 10_000.0,
            })
            previous = close
        histories[asset] = rows
    return histories


def test_frozen_contract_is_exact_and_oos_stays_locked():
    contract = _load_contract()
    assert contract["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert contract["contract_sha256"] == "8d991f723c65a583b1d3188aa7f4f77493d08cfd198ee6aa4be508294d770989"
    assert contract["chronology"]["untouched_oos"] == "LOCKED"
    assert contract["trade_authority"] is False


def test_signal_uses_through_origin_beta_and_no_future_bar():
    contract = _load_contract()
    histories = _validate_histories(_histories(), contract, exact_dataset=False)
    before = _signal(histories, 230, "ETH-USDT-SWAP", contract, gap_min=0.005)
    assert before["eligible"] is True
    assert before["direction"] == "LONG"
    assert 0.5 <= before["beta"] <= 2.0

    poisoned = copy.deepcopy(histories)
    for asset in poisoned:
        for row in poisoned[asset][231:250]:
            for key in ("open", "high", "low", "close"):
                row[key] *= 10
    assert _signal(poisoned, 230, "ETH-USDT-SWAP", contract, gap_min=0.005) == before


def test_no_underreaction_baseline_does_not_require_follower_beta():
    contract = _load_contract()
    histories = _histories(260, impulse=230)
    btc, eth = histories["BTC-USDT-SWAP"], histories["ETH-USDT-SWAP"]
    for i in range(62, 230):
        btc_return = float(btc[i]["close"]) / float(btc[i - 1]["close"]) - 1
        open_price = float(eth[i - 1]["close"])
        close = open_price * (1 + 3 * btc_return)
        eth[i].update(open=open_price, high=max(open_price, close) * 1.001, low=min(open_price, close) * 0.999, close=close)
    clean = _validate_histories(histories, contract, exact_dataset=False)
    assert _signal(clean, 230, "ETH-USDT-SWAP", contract, gap_min=0.005, baseline=True)["eligible"] is True
    assert _signal(clean, 230, "ETH-USDT-SWAP", contract, gap_min=0.005)["reason"] == "BETA_OUTSIDE_RANGE"


def test_next_open_six_hour_portfolio_reconciles_and_shares_event():
    contract = _load_contract()
    histories = _validate_histories(_histories(), contract, exact_dataset=False)
    experiment = _simulate_segment(
        histories, 220, 270, contract, split="TRAINING", gap_min=0.005,
        baseline=False, cost_multiplier=3.0,
        generated_at=datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
    )
    validate_experiment(experiment)
    assert len(experiment["trades"]) == 2
    eth, sol = experiment["trades"]
    assert eth["event_id"] == sol["event_id"]
    assert eth["entry_at"] == sol["entry_at"]
    signal_at = _iso(histories["BTC-USDT-SWAP"][230]["ts"])
    entry_at = _iso(histories["BTC-USDT-SWAP"][231]["ts"])
    assert eth["decision_at"] == signal_at
    assert eth["entry_at"] == entry_at
    assert eth["decision_at"] < eth["entry_at"]
    assert all(value["available_at"] == signal_at for value in eth["features"].values())
    assert eth["notional"] == pytest.approx(sol["notional"])
    assert eth["exit_at"] > eth["entry_at"]
    assert experiment["equity"][0]["gross_exposure"] == 0
    assert experiment["equity"][-1]["gross_exposure"] == 0


def test_real_completion_persists_economics_component_memory_and_rejection(monkeypatch, tmp_path):
    path = tmp_path / "profitability-learning.sqlite"
    Memory(path)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(path))
    selection = run(datetime(2026, 9, 19, 10, tzinfo=timezone.utc))["payload"]["selection"]

    first = persist_selection(selection)
    replay = persist_selection(selection)
    assert replay["training"]["experiment_id"] == first["training"]["experiment_id"]
    assert first["training"]["persistence_status"] == "PERSISTED"
    assert first["training"]["component_evidence"]
    assert first["training"]["component_evidence"][0]["component"]["kind"] == "underreaction"
    snapshot = Memory(path, create=False).snapshot()
    assert len(snapshot["experiments"]) == 2

    candidate = {
        "experiment_id": "repeat-rejected-fingerprint",
        "family": first["training"]["contract"]["family"],
        "strategy_fingerprint": first["training"]["contract"]["strategy_fingerprint"],
        "information_priority": 1.0,
    }
    feedback = apply_queue_feedback({"experiments": [candidate]})["experiments"][0]
    assert feedback["information_priority"] == 0
    assert feedback["learning_feedback"]["reason"] == "rejected_exact_fingerprint"


def test_signal_while_position_is_open_cannot_reenter_at_same_exit_open():
    contract = _load_contract()
    histories = _histories()
    for asset, move in (("BTC-USDT-SWAP", 0.03),
                        ("ETH-USDT-SWAP", 0.005),
                        ("SOL-USDT-SWAP", 0.005)):
        prior = histories[asset][235]["close"]
        close = prior * (1 + move)
        histories[asset][236].update(
            open=prior, high=max(prior, close) * 1.001,
            low=min(prior, close) * 0.999, close=close,
        )
        prior = close
        for index in range(237, len(histories[asset])):
            close = prior * (1 + (0.0002 if index % 2 else -0.0002))
            histories[asset][index].update(
                open=prior, high=max(prior, close) * 1.001,
                low=min(prior, close) * 0.999, close=close,
            )
            prior = close
    clean = _validate_histories(histories, contract, exact_dataset=False)
    experiment = _simulate_segment(
        clean, 220, 270, contract, split="TRAINING", gap_min=0.0,
        baseline=True, cost_multiplier=3.0,
        generated_at=datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
    )
    assert len(experiment["trades"]) == 2
    assert {trade["decision_at"] for trade in experiment["trades"]} == {
        _iso(clean["BTC-USDT-SWAP"][230]["ts"])
    }


def test_bad_alignment_and_capacity_fail_closed():
    contract = _load_contract()
    broken = _histories()
    broken["SOL-USDT-SWAP"][5]["ts"] += 1
    with pytest.raises(ValueError, match="common|hourly"):
        _validate_histories(broken, contract, exact_dataset=False)

    result = evaluate_selection_from_histories({}, contract=contract)
    assert result["screen_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["untouched_oos_opened"] is False
    assert result["trade_authority"] is False


def test_oos_mutation_cannot_change_train_validation_result():
    contract = _load_contract()
    histories = _histories(1000, impulse=500)
    original = evaluate_selection_from_histories(histories, contract=contract)
    poisoned = copy.deepcopy(histories)
    for rows in poisoned.values():
        for row in rows[800:]:
            for key in ("open", "high", "low", "close", "volume", "quote_volume"):
                row[key] *= 1000
    replay = evaluate_selection_from_histories(poisoned, contract=contract)
    assert replay == original


def test_committed_frozen_screen_replays_and_preserves_negative_evidence():
    path = Path("orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        committed = json.load(handle)
    assert verify_research_envelope(committed)
    generated_at = datetime.fromisoformat(committed["payload"]["generated_at"])
    assert run(generated_at) == committed
    selection = committed["payload"]["selection"]
    assert selection["screen_status"] == "PRE_OOS_FAIL"
    assert selection["economic_pre_oos_pass"] is False
    assert selection["untouched_oos_opened"] is False
    assert selection["variants"]["primary_50bps"]["3x"]["validation"]["pooled"]["mean_net_bps"] == pytest.approx(-113.68599715563137)

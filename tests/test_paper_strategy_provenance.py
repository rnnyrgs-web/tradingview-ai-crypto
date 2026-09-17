from pathlib import Path

import pytest

from paper_db import _prepare_paper_signal_decision
import paper_trading
from strategy_contract import freeze_strategy_contract


def _frozen_contract():
    return freeze_strategy_contract({
        "strategy_family": "momentum",
        "strategy_version": "v1",
        "features": {"residual_momentum": {"lookback": 24}},
        "universe": ["BTC"],
        "universe_selection_rules": {"top_n": 1},
        "entry_rules": {"rank_lte": 1},
        "exit_rules": {"horizon_hours": 24},
        "stop_rules": {"max_loss_pct": 2.0},
        "position_sizing": {"equal_weight": True},
        "holding_logic": {"max_hours": 24},
        "timeframes": ["1h"],
        "horizon": "24h",
        "costs": {"fees_bps": 20, "spread_bps": 4, "slippage_bps": 6},
        "train_range": ["2024-01-01", "2024-12-31"],
        "validation_range": ["2025-01-01", "2025-06-30"],
        "untouched_oos_range": ["2025-07-01", "2025-12-31"],
        "git_sha": "git-abc",
        "research_code_sha256": "code-abc",
        "dataset_id": "dataset-001",
        "dataset_sha256": "data-abc",
        "hypothesis_id": "H-001",
        "experiment_id": "EXP-001",
    })


def _forward_gate():
    return {
        "state": "FORWARD_PENDING",
        "blocking_gates": ["genuine_forward"],
        "real_money_trade_authority": False,
    }


def test_paper_signal_decision_preserves_strategy_provenance_fields():
    payload = _prepare_paper_signal_decision({
        "account_id": "default",
        "signal_key": "scan:24h:BTC:LONG",
        "scan_id": "scan",
        "signal_id": "SIG-001",
        "symbol": "BTC",
        "horizon": "24h",
        "direction": "LONG",
        "action": "TRADE",
        "decision": "ACCEPTED",
        "reason": "frozen_strategy_forward_shadow",
        "strategy_fingerprint": "fingerprint-001",
        "experiment_id": "EXP-001",
        "git_sha": "abc123",
        "dataset_sha256": "data123",
        "strategy_contract_sha256": "contract123",
    })
    assert payload["signal_id"] == "SIG-001"
    assert payload["strategy_fingerprint"] == "fingerprint-001"
    assert payload["experiment_id"] == "EXP-001"
    assert payload["git_sha"] == "abc123"
    assert payload["dataset_sha256"] == "data123"
    assert payload["strategy_contract_sha256"] == "contract123"


def test_strategy_provenance_migration_is_append_only():
    sql = Path("migrations/20260916_strategy_provenance.sql").read_text(encoding="utf-8").lower()
    assert "strategy_fingerprint" in sql
    assert "experiment_id" in sql
    assert "dataset_sha256" in sql
    assert "paper_signal_decisions" in sql
    assert "paper_trades" in sql
    assert "cannot be deleted" in sql
    assert "provenance" in sql


def test_runtime_paper_decision_copies_complete_one_edge_provenance(monkeypatch):
    captured = {}
    monkeypatch.setattr(paper_trading, "insert_paper_signal_decision", lambda row: captured.update(row) or True)
    frozen = _frozen_contract()
    row = {
        "scan_id": "scan", "signal_id": "SIG-001", "symbol": "BTC", "horizon": "24h",
        "direction": "LONG", "action": "TRADE", "generated_at": "2026-09-16T12:00:00+00:00",
        "one_edge_candidate": True, "frozen_strategy_contract": frozen, "canonical_gate": _forward_gate(),
    }
    assert paper_trading._record_decision(row, "ACCEPTED", "forward") is True
    assert {key: captured[key] for key in (
        "signal_id", "strategy_fingerprint", "experiment_id", "git_sha",
        "dataset_sha256", "strategy_contract_sha256",
    )} == {
        "signal_id": "SIG-001", "strategy_fingerprint": frozen["fingerprint"], "experiment_id": "EXP-001",
        "git_sha": "git-abc", "dataset_sha256": "data-abc", "strategy_contract_sha256": frozen["fingerprint"],
    }


def test_runtime_paper_decision_fails_closed_for_incomplete_one_edge_provenance(monkeypatch):
    monkeypatch.setattr(paper_trading, "insert_paper_signal_decision", lambda row: True)
    with pytest.raises(RuntimeError, match="frozen strategy contract"):
        paper_trading._record_decision({
            "scan_id": "scan", "signal_id": "SIG-001", "symbol": "BTC", "horizon": "24h",
            "direction": "LONG", "action": "TRADE", "one_edge_candidate": True,
            "strategy_fingerprint": "fp-001",
        }, "ACCEPTED", "forward")


def test_runtime_paper_decision_rejects_forged_provenance_even_when_complete(monkeypatch):
    monkeypatch.setattr(paper_trading, "insert_paper_signal_decision", lambda row: True)
    frozen = _frozen_contract()
    with pytest.raises(RuntimeError, match="does not match frozen strategy contract"):
        paper_trading._record_decision({
            "scan_id": "scan", "signal_id": "SIG-001", "symbol": "BTC", "horizon": "24h",
            "direction": "LONG", "action": "TRADE", "one_edge_candidate": True,
            "frozen_strategy_contract": frozen, "canonical_gate": _forward_gate(),
            "strategy_fingerprint": "forged", "experiment_id": "EXP-001", "git_sha": "git-abc",
            "dataset_sha256": "data-abc", "strategy_contract_sha256": frozen["fingerprint"],
        }, "ACCEPTED", "forward")


def test_runtime_paper_decision_requires_authoritative_forward_pending_state(monkeypatch):
    monkeypatch.setattr(paper_trading, "insert_paper_signal_decision", lambda row: True)
    with pytest.raises(RuntimeError, match="FORWARD_PENDING"):
        paper_trading._record_decision({
            "scan_id": "scan", "signal_id": "SIG-001", "symbol": "BTC", "horizon": "24h",
            "direction": "LONG", "action": "TRADE", "one_edge_candidate": True,
            "frozen_strategy_contract": _frozen_contract(),
            "canonical_gate": {"state": "OOS_PASS", "real_money_trade_authority": False},
        }, "ACCEPTED", "forward")

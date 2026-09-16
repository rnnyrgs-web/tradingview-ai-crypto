from pathlib import Path

from paper_db import _prepare_paper_signal_decision


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

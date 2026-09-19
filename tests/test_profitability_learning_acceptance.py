import gzip
import json

import continuous_coordinator as coordinator
import profitability_learning.acceptance as acceptance
from profitability_learning.acceptance import (
    acceptance_snapshot,
    run_canonical_acceptance,
)
from profitability_learning.memory import Memory


def test_canonical_runtime_acceptance_persists_rejection_and_is_replay_safe(
    monkeypatch, tmp_path
):
    database = tmp_path / "profitability-learning.sqlite"
    Memory(database)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(database))

    first = run_canonical_acceptance()
    replay = run_canonical_acceptance()

    assert first["status"] == "PASSED"
    assert first["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert first["persistence"] == {
        "experiment_count": 2,
        "new_experiment_count": 2,
        "replay_experiment_count": 2,
        "duplicate_suppressed": True,
        "training_experiment_id": "0bc7d582a0730149242d700d848f5fb23c16c2fdea35944579587c1c813f2b97",
        "validation_experiment_id": "806f6bd58d69a3ad1d81c7191f06cf564be2dfbfc8697f889eff3038426ac696",
    }
    assert first["admission"] == {
        "exact_rejected_fingerprint_veto": True,
        "learning_factor": 0.0,
        "reason": "rejected_exact_fingerprint",
    }
    assert first["learning"] == {
        "component_kind": "underreaction",
        "component_evidence_level": "DEVELOPMENT_ASSOCIATION",
        "component_proven": False,
        "learning_mission_generated": True,
        "learning_mission_mode": "LEARN",
    }
    assert replay["status"] == "PASSED"
    assert replay["persistence"]["new_experiment_count"] == 0
    assert replay["persistence"]["duplicate_suppressed"] is True
    assert replay["research_only"] is True
    assert replay["trade_authority"] is False
    assert replay["promotion_authority"] is False
    assert replay["broker_connected"] is False


def test_invalid_acceptance_artifact_fails_closed_without_writing_memory(
    monkeypatch, tmp_path
):
    database = tmp_path / "profitability-learning.sqlite"
    Memory(database)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(database))
    artifact = tmp_path / "invalid.json.gz"
    with gzip.open(artifact, "wt", encoding="utf-8") as handle:
        json.dump({"payload": {"selection": {"fingerprint_id": "wrong"}}}, handle)

    result = run_canonical_acceptance(artifact)

    assert result["status"] == "WAIT_INVALID_ARTIFACT"
    assert result["required_action"] == "Restore the exact sealed canonical acceptance artifact"
    assert Memory(database, create=False).snapshot()["experiments"] == []
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False


def test_missing_or_corrupt_configured_memory_is_not_reset(monkeypatch, tmp_path):
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(missing))

    missing_result = run_canonical_acceptance()

    assert missing_result["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert not missing.exists()

    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(corrupt))

    corrupt_result = run_canonical_acceptance()

    assert corrupt_result["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert corrupt.read_bytes() == b"not a sqlite database"
    assert corrupt_result["trade_authority"] is False
    assert corrupt_result["promotion_authority"] is False


def test_durable_memory_outage_fails_closed(monkeypatch):
    def unavailable():
        raise ConnectionError("simulated durable-memory outage")

    monkeypatch.setattr(acceptance, "learning_snapshot", unavailable)

    result = run_canonical_acceptance()

    assert result["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["broker_connected"] is False


def test_coordinator_exposes_only_compact_acceptance_status(monkeypatch, tmp_path):
    database = tmp_path / "profitability-learning.sqlite"
    Memory(database)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(database))

    initialized = coordinator.initialize_profitability_acceptance()
    response = coordinator.profitability_acceptance()

    assert initialized == response == acceptance_snapshot()
    assert response["status"] == "PASSED"
    assert "contract" not in json.dumps(response)
    assert "trades" not in json.dumps(response)
    assert response["trade_authority"] is False

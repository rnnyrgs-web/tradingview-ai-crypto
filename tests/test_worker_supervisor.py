import json
from pathlib import Path

from worker_supervisor import (
    classify_failure,
    incident_fingerprint,
    record_incident,
    supervisor_summary,
    worker_health,
)


def test_failure_classification_is_conservative():
    assert classify_failure(-9, "TimeoutError") == "timeout"
    assert classify_failure(-1, "NetworkError") == "network_or_exchange"
    assert classify_failure(-1, "EvidenceSummaryError") == "malformed_or_invalid_evidence"
    assert classify_failure(-1, "MemoryError") == "resource_or_runtime"
    assert classify_failure(2, None) == "process_failure"
    assert classify_failure(0, None) == "none"


def test_incident_fingerprint_is_deterministic_and_worker_specific():
    a = incident_fingerprint("major-btc", "timeout", "TimeoutError", -9)
    b = incident_fingerprint("major-btc", "timeout", "TimeoutError", -9)
    c = incident_fingerprint("major-eth", "timeout", "TimeoutError", -9)
    assert a == b
    assert a != c
    assert len(a) == 20


def test_record_incident_is_append_only_and_has_no_authority(tmp_path):
    ledger = tmp_path / "incidents.jsonl"
    incident = record_incident("major-btc", -9, "TimeoutError", ledger_path=ledger)
    record_incident("major-btc", -9, "TimeoutError", ledger_path=ledger)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["fingerprint"] == rows[1]["fingerprint"]
    assert incident["classification"] == "timeout"
    assert incident["trade_authority"] is False
    assert incident["promotion_authority"] is False
    assert incident["write_authority"] is False


def test_worker_health_detects_stale_and_crashed_workers():
    healthy = worker_health(
        {"state": "running", "heartbeat_monotonic": 900.0},
        now_monotonic=1000.0,
        job_timeout_seconds=300,
        grace_seconds=120,
    )
    stale = worker_health(
        {"state": "running", "heartbeat_monotonic": 400.0},
        now_monotonic=1000.0,
        job_timeout_seconds=300,
        grace_seconds=120,
    )
    crashed = worker_health(
        {"state": "crashed", "heartbeat_monotonic": 999.0},
        now_monotonic=1000.0,
        job_timeout_seconds=300,
        grace_seconds=120,
    )
    assert healthy["healthy"] is True
    assert stale["stale"] is True and stale["healthy"] is False
    assert crashed["crashed"] is True and crashed["healthy"] is False


def test_supervisor_summary_fails_closed_and_has_no_authority():
    summary = supervisor_summary(
        {
            "a": {"state": "running", "heartbeat_monotonic": 995.0},
            "b": {"state": "crashed", "heartbeat_monotonic": 995.0},
        },
        now_monotonic=1000.0,
        job_timeout_seconds=300,
    )
    assert summary["healthy"] is False
    assert summary["crashed_workers"] == ["b"]
    assert summary["trade_authority"] is False
    assert summary["promotion_authority"] is False
    assert summary["write_authority"] is False

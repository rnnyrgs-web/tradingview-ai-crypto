from pathlib import Path

import continuous_worker_army as army


def test_read_diagnostic_tail_is_bounded_and_redacted(tmp_path):
    path = tmp_path / "stderr.log"
    path.write_text(
        "x" * 20000
        + "\nAuthorization: Bearer very-secret-token-value\n"
        + "ValueError: final failure reason\n",
        encoding="utf-8",
    )
    diagnostic = army._read_diagnostic_tail(path)
    assert len(diagnostic) <= 8020
    assert "very-secret-token-value" not in diagnostic
    assert "ValueError: final failure reason" in diagnostic


def test_public_snapshot_never_contains_private_diagnostic_excerpt():
    with army._lock:
        original = army._status["workers"]
        army._status["workers"] = {
            "test": {
                "state": "error_backoff",
                "script": "research_runner.py",
                "last_incident": {
                    "fingerprint": "abc",
                    "diagnostic_fingerprint": "def",
                    "trade_authority": False,
                },
                "heartbeat_at": "now",
                "heartbeat_monotonic": 1.0,
            }
        }
    try:
        snap = army.snapshot()
        assert "diagnostic_excerpt" not in str(snap)
    finally:
        with army._lock:
            army._status["workers"] = original

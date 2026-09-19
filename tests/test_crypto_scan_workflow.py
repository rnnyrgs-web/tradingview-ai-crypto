from pathlib import Path


WORKFLOW = Path(".github/workflows/crypto_scan.yml")
DRAIN = Path(".github/workflows/pending_prediction_drain.yml")


def test_legacy_crypto_scan_is_manual_only_and_never_calls_scan_or_evaluate():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "/scan" not in text
    assert "/evaluate" not in text
    assert "Legacy signal generation is retired" in text


def test_pending_prediction_drain_is_temporary_and_cannot_generate_new_signals():
    text = DRAIN.read_text(encoding="utf-8")
    assert 'cron: "23 * * * *"' in text
    assert "2026-10-01T00:00:00Z" in text
    assert "/research/resolve-pending" in text
    assert "/scan" not in text
    assert "SCAN_SECRET" in text
    assert "timeout-minutes: 5" in text

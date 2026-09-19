from pathlib import Path


def test_no_new_calibration_scan_runs_after_signal_retirement():
    scan = Path(".github/workflows/crypto_scan.yml").read_text(encoding="utf-8")
    drain = Path(".github/workflows/pending_prediction_drain.yml").read_text(encoding="utf-8")
    assert "schedule:" not in scan
    assert "/scan" not in scan
    assert "/research/resolve-pending" in drain
    assert "/scan" not in drain

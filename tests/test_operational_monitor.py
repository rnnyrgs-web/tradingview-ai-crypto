import operational_monitor as monitor


def test_health_monitor_sanitizes_errors_and_summarizes_scan():
    try:
        raise RuntimeError("private upstream response")
    except RuntimeError as exc:
        monitor.record_error("scan", exc)
    monitor.record_scan({
        "scan_id": "scan-1",
        "ok": True,
        "universe_count": 80,
        "deep_scanned": 40,
        "scan_error_count": 1,
        "signals_saved": 0,
        "ai_error": None,
        "opportunity_error": None,
    })

    health = monitor.health_snapshot()
    assert health["last_scan"]["scan_id"] == "scan-1"
    assert health["last_scan"]["ai_ok"] is True
    assert health["recent_errors"][-1]["error_type"] == "RuntimeError"
    assert "private upstream response" not in str(health)

import research_observability as obs


def test_adaptive_accuracy_evidence_is_visible_but_non_authoritative(tmp_path):
    evidence = {
        "evidence_conclusion": "validation_failed",
        "oos_opened": False,
        "experiment": {
            "experiment_id": "exp-123",
            "dimension": "market_regime",
            "group": "BEAR",
            "effective_horizon": "24h",
            "validation_passed": False,
            "status": "VALIDATION_FAILED_OOS_CLOSED",
        },
        "research_memory": {"lesson_count": 7},
        "trade_authority": False,
        "promotion_authority": False,
        "research_only": True,
    }

    obs.record_worker_result("adaptive-accuracy", 0, 8.5, evidence, metrics_dir=tmp_path)
    snap = obs.snapshot(metrics_dir=tmp_path)
    adaptive = snap["adaptive_accuracy"]

    assert adaptive["last_exit_code"] == 0
    assert adaptive["elapsed_seconds"] == 8.5
    assert adaptive["latest_evidence"] == evidence
    assert adaptive["latest_evidence"]["oos_opened"] is False
    assert snap["trade_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["signal_authority"] is False
    assert snap["research_only"] is True


def test_missing_adaptive_accuracy_evidence_fails_closed(tmp_path):
    snap = obs.snapshot(metrics_dir=tmp_path)
    adaptive = snap["adaptive_accuracy"]
    assert adaptive["last_exit_code"] is None
    assert adaptive["latest_evidence"] is None
    assert snap["trade_authority"] is False

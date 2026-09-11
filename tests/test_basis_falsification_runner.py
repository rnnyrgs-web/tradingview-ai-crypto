import basis_falsification_runner as runner


def test_runner_is_research_only_and_never_exposes_raw_points(monkeypatch):
    monkeypatch.setattr(
        runner,
        "collect_okx_basis_history",
        lambda base, target_points, max_pages: {
            "research_only": True,
            "candidate_id": "DATA-BASIS-001",
            "available": True,
            "reason": None,
            "target_points": 1000,
            "point_count": 1000,
            "mark_point_count": 1000,
            "index_point_count": 1000,
            "mark_pages": 10,
            "index_pages": 10,
            "alignment": "exact_shared_timestamp_only",
            "completed_candles_only": True,
            "interpolation_allowed": False,
            "points": [{"ts": 1, "basis_bps": 1.0}],
            "index_points": [{"ts": 1, "value": 100.0}],
        },
    )
    monkeypatch.setattr(
        runner,
        "evaluate_primary_horizons",
        lambda dataset: {
            "research_only": True,
            "results": {
                "24": {"research_only": True, "available": True, "oos_samples": 8},
                "168": {"research_only": True, "available": False, "reason": "insufficient_oos_samples_before_scoring"},
            },
            "production_authority": False,
            "promotion_authority": False,
        },
    )

    result = runner.run()

    assert result["task_id"] == "COORD-DATA-003"
    assert result["candidate_id"] == "DATA-BASIS-001"
    assert result["evidence_conclusion"] == "stage1_evaluated"
    assert result["available_primary_results"] == 1
    assert "points" not in result["collection"]
    assert "index_points" not in result["collection"]
    assert result["collection"]["alignment"] == "exact_shared_timestamp_only"
    assert result["collection"]["completed_candles_only"] is True
    assert result["collection"]["interpolation_allowed"] is False
    assert result["production_authority"] is False
    assert result["signal_authority"] is False
    assert result["paper_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_authority"] is False


def test_runner_keeps_insufficient_evidence_fail_closed(monkeypatch):
    monkeypatch.setattr(
        runner,
        "collect_okx_basis_history",
        lambda base, target_points, max_pages: {
            "research_only": True,
            "candidate_id": "DATA-BASIS-001",
            "available": False,
            "reason": "insufficient_exact_timestamp_coverage",
            "target_points": 1000,
            "point_count": 300,
            "mark_point_count": 300,
            "index_point_count": 300,
            "mark_pages": 20,
            "index_pages": 20,
            "alignment": "exact_shared_timestamp_only",
            "completed_candles_only": True,
            "interpolation_allowed": False,
        },
    )
    monkeypatch.setattr(
        runner,
        "evaluate_primary_horizons",
        lambda dataset: {
            "research_only": True,
            "results": {
                "24": {"research_only": True, "available": False, "reason": "dataset_unavailable"},
                "168": {"research_only": True, "available": False, "reason": "dataset_unavailable"},
            },
            "production_authority": False,
            "promotion_authority": False,
        },
    )

    result = runner.run()

    assert result["evidence_conclusion"] == "insufficient_evidence"
    assert result["available_primary_results"] == 0
    assert result["collection"]["available"] is False
    assert result["promotion_authority"] is False

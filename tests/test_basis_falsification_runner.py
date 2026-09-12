import basis_falsification_runner as runner


def test_compatibility_runner_is_now_frozen_funding_candidate():
    assert runner.DEFAULT_FUNDING_TARGET_POINTS == 1200
    assert runner.DEFAULT_INDEX_TARGET_POINTS == 5000
    assert runner.DEFAULT_FUNDING_MAX_PAGES == 15
    assert runner.DEFAULT_INDEX_MAX_PAGES == 50
    assert runner.SUMMARY_ENV == "BASIS_FALSIFICATION_SUMMARY_PATH"


def test_runner_bounds_collection_without_outcome_tuning(monkeypatch):
    monkeypatch.setenv("FUNDING_RESEARCH_TARGET_POINTS", "999999")
    monkeypatch.setenv("FUNDING_RESEARCH_INDEX_TARGET_POINTS", "999999")
    monkeypatch.setenv("FUNDING_RESEARCH_MAX_PAGES", "999999")
    monkeypatch.setenv("FUNDING_RESEARCH_INDEX_MAX_PAGES", "999999")
    assert runner._configured_evidence_window() == (2000, 5000, 20, 50)


def test_runner_is_research_only_and_never_exposes_raw_points(monkeypatch):
    monkeypatch.setattr(
        runner,
        "collect_okx_funding_history",
        lambda base, funding_target_points, index_target_points, funding_max_pages, index_max_pages: {
            "research_only": True,
            "candidate_id": "DATA-FUNDING-001",
            "available": True,
            "reason": None,
            "funding_point_count": 1200,
            "index_point_count": 5000,
            "funding_pages": 12,
            "index_pages": 50,
            "uses_actual_funding_timestamps": True,
            "assumed_fixed_funding_interval": False,
            "completed_price_candles_only": True,
            "interpolation_allowed": False,
            "forward_fill_allowed": False,
            "nearest_neighbor_matching": False,
            "funding_points": [{"ts": 1, "value": 0.0001}],
            "index_points": [{"ts": 1, "value": 100.0}],
        },
    )
    monkeypatch.setattr(
        runner,
        "evaluate_primary_horizons",
        lambda dataset: {
            "research_only": True,
            "candidate_id": "DATA-FUNDING-001",
            "results": {
                "24": {"research_only": True, "available": True, "oos_samples": 20, "stage1_pass": False},
                "168": {"research_only": True, "available": True, "oos_samples": 9, "stage1_pass": True},
            },
            "production_authority": False,
            "promotion_authority": False,
        },
    )

    result = runner.run()

    assert result["task_id"] == "COORD-DATA-004"
    assert result["candidate_id"] == "DATA-FUNDING-001"
    assert result["legacy_runtime_filename"] == "basis_falsification_runner.py"
    assert result["evidence_conclusion"] == "stage1_evaluated"
    assert result["available_primary_results"] == 2
    assert result["stage1_pass_count"] == 1
    assert "funding_points" not in result["collection"]
    assert "index_points" not in result["collection"]
    assert result["collection"]["uses_actual_funding_timestamps"] is True
    assert result["collection"]["assumed_fixed_funding_interval"] is False
    assert result["collection"]["completed_price_candles_only"] is True
    assert result["collection"]["interpolation_allowed"] is False
    assert result["collection"]["forward_fill_allowed"] is False
    assert result["collection"]["nearest_neighbor_matching"] is False
    assert result["production_authority"] is False
    assert result["signal_authority"] is False
    assert result["paper_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_authority"] is False


def test_runner_keeps_insufficient_evidence_fail_closed(monkeypatch):
    monkeypatch.setattr(
        runner,
        "collect_okx_funding_history",
        lambda base, funding_target_points, index_target_points, funding_max_pages, index_max_pages: {
            "research_only": True,
            "candidate_id": "DATA-FUNDING-001",
            "available": False,
            "reason": "insufficient_raw_history",
            "funding_point_count": 1,
            "index_point_count": 200,
            "funding_pages": 1,
            "index_pages": 2,
            "uses_actual_funding_timestamps": True,
            "assumed_fixed_funding_interval": False,
            "completed_price_candles_only": True,
            "interpolation_allowed": False,
            "forward_fill_allowed": False,
            "nearest_neighbor_matching": False,
        },
    )
    monkeypatch.setattr(
        runner,
        "evaluate_primary_horizons",
        lambda dataset: {
            "research_only": True,
            "candidate_id": "DATA-FUNDING-001",
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
    assert result["stage1_pass_count"] == 0
    assert result["collection"]["available"] is False
    assert result["promotion_authority"] is False

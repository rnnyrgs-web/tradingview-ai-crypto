import inspect

import basis_falsification_runner as runner


def test_compatibility_runner_preserves_summary_transport_only():
    assert runner.SUMMARY_ENV == "BASIS_FALSIFICATION_SUMMARY_PATH"


def test_rejected_funding_fingerprint_is_retired_without_collection_or_evaluation():
    result = runner.run()

    assert result["task_id"] == "COORD-DATA-004"
    assert result["candidate_id"] == "DATA-FUNDING-001"
    assert result["legacy_runtime_filename"] == "basis_falsification_runner.py"
    assert result["evidence_conclusion"] == "retired_rejected_fingerprint"
    assert result["retired"] is True
    assert result["retirement_reason"] == "candidate_rejected_no_material_condition_change"
    assert result["market_data_requests"] == 0
    assert result["evaluation_performed"] is False
    assert result["production_authority"] is False
    assert result["signal_authority"] is False
    assert result["paper_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_authority"] is False


def test_retired_runtime_cannot_silently_reintroduce_funding_fetch_or_scoring():
    source = inspect.getsource(runner)
    assert "collect_okx_funding_history" not in source
    assert "evaluate_primary_horizons" not in source
    assert "funding_history_research" not in source
    assert "funding_falsification_research" not in source

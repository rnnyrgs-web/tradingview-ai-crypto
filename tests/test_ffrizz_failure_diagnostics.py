from research_adaptive_accuracy_runner import _bounded_ffrizz_failure


def test_ffrizz_prediction_ledger_failure_exposes_only_bounded_stage_and_status_class():
    diagnostic = _bounded_ffrizz_failure(
        RuntimeError("Supabase prediction ledger insert failed: 400 secret-response-body")
    )

    assert diagnostic == {
        "error_type": "RuntimeError",
        "error_stage": "prediction_ledger_persistence",
        "http_status_class": "http_4xx",
    }
    assert "secret-response-body" not in repr(diagnostic)


def test_ffrizz_non_persistence_failure_stays_generic_and_bounded():
    diagnostic = _bounded_ffrizz_failure(RuntimeError("private symbol or provider detail"))

    assert diagnostic == {
        "error_type": "RuntimeError",
        "error_stage": "ffrizz_collection_or_scoring",
        "http_status_class": None,
    }
    assert "private symbol or provider detail" not in repr(diagnostic)

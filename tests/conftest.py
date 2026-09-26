from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

import big_move_source_authenticity as source_authenticity
from orchestration.strategy_behavior_schema import allow_test_behavior_schemas

# Only regression modules that intentionally exercise synthetic TEST_* behavior
# contracts receive the explicit test-only resolver context. Production-boundary
# tests are deliberately absent from this allowlist so the default production
# resolver is exercised there.
_TEST_BEHAVIOR_SCHEMA_MODULES = {
    "test_scientific_design_identity.py",
    "test_strategy_behavior_field_semantics.py",
    "test_strategy_behavior_identity.py",
    "test_strategy_predeclaration.py",
    "test_strategy_predeclaration_scalar_representation_guard.py",
}

# These three tests exercise cohort coverage accounting rather than archive-origin
# chronology. Their historical primary documents are synthetic local fixtures that
# intentionally have no Common Crawl acquisition bundle. Isolate that unrelated
# boundary in the tests only; dedicated primary-document chronology regressions must
# continue through the real fail-closed validator.
_COHORT_ACCOUNTING_TESTS_WITH_SYNTHETIC_PRIMARY_CHRONOLOGY = {
    "test_ready_requires_source_native_proof_and_frozen_thresholds",
    "test_sparse_asset_does_not_count_toward_minimum",
    "test_duplicate_decision_rows_cannot_inflate_coverage",
}


@pytest.fixture(autouse=True)
def _explicit_test_behavior_schema_context(request: pytest.FixtureRequest):
    filename = Path(str(request.node.path)).name
    context = (
        allow_test_behavior_schemas()
        if filename in _TEST_BEHAVIOR_SCHEMA_MODULES
        else nullcontext()
    )
    with context:
        yield


@pytest.fixture(autouse=True)
def _isolate_synthetic_primary_chronology_for_coverage_accounting(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
):
    filename = Path(str(request.node.path)).name
    if (
        filename == "test_big_move_cohort_preflight.py"
        and request.node.name in _COHORT_ACCOUNTING_TESTS_WITH_SYNTHETIC_PRIMARY_CHRONOLOGY
    ):
        def _test_only_historical_capture(*args, **kwargs):
            return {
                "status": "BOUND_TEST_ONLY_SYNTHETIC_CHRONOLOGY",
                "authority": "TEST_ONLY_NO_PRODUCTION_OR_SCIENTIFIC_AUTHORITY",
            }

        monkeypatch.setattr(
            source_authenticity,
            "validate_primary_document_historical_availability",
            _test_only_historical_capture,
        )
    yield

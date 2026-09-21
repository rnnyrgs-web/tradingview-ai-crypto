from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

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

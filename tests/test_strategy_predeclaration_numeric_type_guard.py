from __future__ import annotations

import math

import pytest

from orchestration.strategy_predeclaration import _require_nonnegative_number


def test_cost_identity_guard_accepts_only_native_finite_json_numbers() -> None:
    assert _require_nonnegative_number(10, "cost") == 10.0
    assert _require_nonnegative_number(10.0, "cost") == 10.0
    assert _require_nonnegative_number(0.0, "cost") == 0.0

    for value in ("10", "10.0", True, None, math.inf, -math.inf, math.nan):
        with pytest.raises(RuntimeError, match="finite JSON number|numeric"):
            _require_nonnegative_number(value, "cost")


def test_cost_identity_guard_still_rejects_negative_numbers() -> None:
    with pytest.raises(RuntimeError, match="non-negative"):
        _require_nonnegative_number(-0.5, "cost")

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_randomized_placebo import (
    _validate_contract,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration/external_replication/ext_abnormal_day_momentum_001_randomized_timing_placebo.json"
)


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_runtime_rejects_mutated_seed_with_stale_frozen_contract_digest() -> None:
    """The one pre-outcome placebo draw must not be caller-reseedable after outcomes."""
    contract = _contract()
    contract["formation"]["seed_uint64"] ^= 1

    with pytest.raises(RuntimeError, match="contract|digest|frozen|pin"):
        _validate_contract(contract)


def test_runtime_rejects_mutated_validation_window_with_stale_contract_digest() -> None:
    """A caller must not move the frozen placebo search window after outcomes."""
    contract = _contract()
    contract["frozen_windows"]["validation_first_end_utc"] = "2026-06-29T23:00:00Z"

    with pytest.raises(RuntimeError, match="contract|digest|frozen|pin"):
        _validate_contract(contract)

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from orchestration.rejected_fingerprints import load_rejected_fingerprints
from orchestration.scientific_design_identity import (
    strategy_behavior_projection,
    strategy_behavior_sha256,
)
from orchestration.strategy_behavior_revision import (
    COHORT_001_OHLCV_REVISION_2_SCHEMAS,
    behavior_schema_executable_contract_revision,
)
from orchestration.strategy_behavior_schema import (
    BEHAVIOR_SCHEMA_REGISTRY_VERSION,
    resolve_behavior_schema_id,
)
from orchestration.strategy_behavior_value_contract import BEHAVIOR_VALUE_CONTRACT_VERSION
from orchestration.strategy_factory_cohort_001_admission import resolve_candidate_predeclaration

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "orchestration" / "cohorts" / "strategy_factory_cohort_001_seed.json"


def _resolved_candidate(fingerprint_id: str) -> dict:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    candidate = next(
        row for row in seed["candidates"] if row["fingerprint_id"] == fingerprint_id
    )
    return resolve_candidate_predeclaration(seed, candidate)


def _projection_sha256(projection: dict) -> str:
    encoded = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_scoped_revision_keeps_global_rejected_memory_domains_stable() -> None:
    assert BEHAVIOR_SCHEMA_REGISTRY_VERSION == 1
    assert BEHAVIOR_VALUE_CONTRACT_VERSION == 1

    entries = load_rejected_fingerprints()
    reconstructible = [
        entry
        for entry in entries
        if isinstance(entry.get("projection"), dict)
        and isinstance(entry.get("strategy_behavior_sha256"), str)
    ]
    assert reconstructible
    for entry in reconstructible:
        assert strategy_behavior_sha256(entry["projection"]) == entry[
            "strategy_behavior_sha256"
        ]
        schema_id = resolve_behavior_schema_id(entry["projection"])
        assert behavior_schema_executable_contract_revision(schema_id) == 1


def test_only_changed_cohort_ohlcv_schemas_receive_revision_two() -> None:
    assert COHORT_001_OHLCV_REVISION_2_SCHEMAS == {
        "C101_BREADTH_PERSIST_V1",
        "C101_RESIDUAL_REV_V1",
        "C101_SIGNED_VOLUME_DRIFT_V1",
        "C101_LOWVOL_DRIFT_REV_V1",
        "C101_WEEKEND_NORMALIZE_V1",
        "C101_MODERATEVOL_AUTOCORR_V1",
        "C101_RANGE_AUCTION_REV_V1",
    }
    for schema_id in COHORT_001_OHLCV_REVISION_2_SCHEMAS:
        assert behavior_schema_executable_contract_revision(schema_id) == 2

    assert behavior_schema_executable_contract_revision("C101_DELTA_CARRY_V1") == 1
    assert behavior_schema_executable_contract_revision("DISC_BTC_LEADLAG_V1") == 1
    with pytest.raises(RuntimeError, match="unknown behavior schema id"):
        behavior_schema_executable_contract_revision("C101_UNKNOWN_V1")


def test_cohort_revision_two_is_domain_bound_without_rewriting_revision_one() -> None:
    candidate = _resolved_candidate("DISC-RESIDUAL-REV-001-v1")
    projection = strategy_behavior_projection(candidate)
    binding = projection["_behavior_schema"]

    assert binding["schema_id"] == "C101_RESIDUAL_REV_V1"
    assert binding["executable_contract_revision"] == 2

    hypothetical_legacy_revision_one = copy.deepcopy(projection)
    hypothetical_legacy_revision_one["_behavior_schema"].pop(
        "executable_contract_revision"
    )
    assert _projection_sha256(hypothetical_legacy_revision_one) != strategy_behavior_sha256(
        candidate
    )


def test_scoped_revision_preserves_dataset_instance_invariance_and_cost_sensitivity() -> None:
    candidate = _resolved_candidate("DISC-RESIDUAL-REV-001-v1")
    original = strategy_behavior_sha256(candidate)

    rehashed_dataset = copy.deepcopy(candidate)
    rehashed_dataset["data_contract"]["normalized_rows_sha256"] = "f" * 64
    rehashed_dataset["data_contract"]["normalized_row_count"] += 1
    assert strategy_behavior_sha256(rehashed_dataset) == original

    changed_cost = copy.deepcopy(candidate)
    changed_cost["cost_model"]["adverse_funding_allowance_bps_per_trade"] = 5.0
    assert strategy_behavior_sha256(changed_cost) != original

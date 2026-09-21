from __future__ import annotations

import json
from pathlib import Path

from orchestration.strategy_factory_cohort_001_admission import (
    build_canonical_admission_receipt,
    resolve_candidate_predeclaration,
)
from orchestration.strategy_predeclaration import freeze_predeclaration


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "orchestration" / "cohorts" / "strategy_factory_cohort_001_seed.json"


def _seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_cohort_001_all_eight_resolve_through_canonical_production_admission() -> None:
    seed = _seed()
    frozen = [
        freeze_predeclaration(resolve_candidate_predeclaration(seed, candidate))
        for candidate in seed["candidates"]
    ]

    assert len(frozen) == 8
    assert len({row["fingerprint_id"] for row in frozen}) == 8
    assert len({row["strategy_behavior_sha256"] for row in frozen}) == 8
    assert len({row["scientific_design_sha256"] for row in frozen}) == 8
    assert len({row["contract_sha256"] for row in frozen}) == 8


def test_cohort_001_admission_receipt_binds_protected_safe_dataset_qualification() -> None:
    receipt = build_canonical_admission_receipt()
    dataset = receipt["selection_dataset_qualification"]

    assert receipt["schema_version"] == 2
    assert dataset["status"] == "QUALIFIED_DEVELOPMENT_ONLY"
    assert dataset["source_dataset_sha256"] == (
        "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
    )
    assert dataset["development_end_utc"] == "2026-08-31T23:00:00+00:00"
    assert dataset["protected_start_utc"] == "2026-09-01T00:00:00+00:00"
    assert dataset["protected_ohlcv_json_decoded"] is False
    assert dataset["economic_outcomes_computed"] is False
    assert dataset["strategy_signals_computed"] is False
    assert len(dataset["receipt_sha256"]) == 64


def test_cohort_001_admission_receipt_preserves_fail_closed_execution_holds() -> None:
    receipt = build_canonical_admission_receipt()
    by_status: dict[str, list[str]] = {}
    for row in receipt["candidates"]:
        by_status.setdefault(row["status"], []).append(row["fingerprint_id"])

    assert set(by_status.get("ADMITTED_DATA_QUALIFIED", [])) == {
        "DISC-RESIDUAL-REV-001-v1",
        "DISC-SIGNED-VOLUME-DRIFT-001-v1",
        "DISC-LOWVOL-DRIFT-REV-001-v1",
        "DISC-MODERATEVOL-AUTOCORR-001-v1",
        "DISC-RANGE-AUCTION-REV-001-v1",
    }
    assert by_status.get("ADMITTED_DATA_QUALIFIED_POWER_RISK") == [
        "DISC-WEEKEND-NORMALIZE-001-v1"
    ]
    assert by_status.get("HOLD_ACTIVE_OWNERSHIP_COLLISION") == [
        "DISC-BREADTH-PERSIST-001-v1"
    ]
    assert by_status.get("DATA_BLOCKED") == ["DISC-DELTA-CARRY-001-v1"]
    assert "REJECTED_CANONICAL_ADMISSION" not in by_status

    authorized = [row for row in receipt["candidates"] if row["screening_authority"]]
    assert len(authorized) == 6
    for row in authorized:
        assert row["selection_dataset_receipt_sha256"] == receipt[
            "selection_dataset_qualification"
        ]["receipt_sha256"]

    held = [row for row in receipt["candidates"] if not row["screening_authority"]]
    assert len(held) == 2
    assert all(row["selection_dataset_receipt_sha256"] is None for row in held)

    assert receipt["planned_hypothesis_count"] == 8
    assert receipt["outcomes_read"] is False
    assert receipt["protected_oos_opened"] is False
    assert receipt["genuine_forward_opened"] is False
    assert receipt["deep_candidate_promoted"] is False
    assert receipt["broker_connected"] is False
    assert receipt["trade_authority"] is False


def test_cohort_001_receipt_is_deterministic_and_old_inline_hashes_are_ignored() -> None:
    first = build_canonical_admission_receipt()
    second = build_canonical_admission_receipt()
    assert first == second

    seed = _seed()
    first_candidate = seed["candidates"][0]
    resolved = resolve_candidate_predeclaration(seed, first_candidate)
    frozen = freeze_predeclaration(resolved)

    # The legacy seed hashes were explicitly marked non-authoritative. The resolver
    # must never copy them into the final frozen predeclaration.
    assert frozen["scientific_design_sha256"] != first_candidate["scientific_design_sha256"]
    assert frozen["contract_sha256"] != first_candidate["contract_sha256"]
    assert len(frozen["strategy_behavior_sha256"]) == 64


def test_cohort_001_common_selection_boundary_stays_development_only() -> None:
    seed = _seed()
    common = seed["common_ohlcv_contract"]
    data = common["data_contract"]

    assert data["normalized_rows_sha256"] == (
        "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
    )
    assert data["selection_validation_end_utc"] == "2026-08-31T23:00:00+00:00"
    assert data["protected_oos_start_utc"] == "2026-09-01T00:00:00+00:00"
    assert data["point_in_time"] is True
    assert data["screen_may_read_protected_oos"] is False

    receipt = build_canonical_admission_receipt()
    for row in receipt["candidates"]:
        assert row.get("untouched_oos_opened", False) is False
        assert row.get("genuine_forward_opened", False) is False
        assert row.get("broker_connected", False) is False
        assert row.get("trade_authority", False) is False

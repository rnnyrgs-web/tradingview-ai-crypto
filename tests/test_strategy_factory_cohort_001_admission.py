from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestration import strategy_factory_cohort_001_admission as admission
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

    assert receipt["schema_version"] == 4
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

    authorized = [row for row in receipt["candidates"] if row["admission_eligible"]]
    assert len(authorized) == 6
    for row in authorized:
        assert row["selection_dataset_receipt_sha256"] == receipt[
            "selection_dataset_qualification"
        ]["receipt_sha256"]

    held = [row for row in receipt["candidates"] if not row["admission_eligible"]]
    assert len(held) == 2
    assert all(row["selection_dataset_receipt_sha256"] is None for row in held)

    assert receipt["planned_hypothesis_count"] == 8
    assert receipt["outcomes_read"] is False
    assert receipt["protected_oos_opened"] is False
    assert receipt["genuine_forward_opened"] is False
    assert receipt["deep_candidate_promoted"] is False
    assert receipt["broker_connected"] is False
    assert receipt["trade_authority"] is False


def test_cohort_001_receipt_is_deterministic_and_inline_hashes_match() -> None:
    first = build_canonical_admission_receipt()
    second = build_canonical_admission_receipt()
    assert first == second

    seed = _seed()
    for candidate in seed["candidates"]:
        frozen = freeze_predeclaration(resolve_candidate_predeclaration(seed, candidate))
        for field in ("scientific_design_sha256", "strategy_behavior_sha256", "contract_sha256"):
            assert candidate[field] == frozen[field]


@pytest.mark.parametrize("candidate_index", range(8))
@pytest.mark.parametrize("field", ("scientific_design_sha256", "strategy_behavior_sha256", "contract_sha256"))
@pytest.mark.parametrize("mutation", ("missing", "mismatched"))
def test_cohort_001_missing_or_mismatched_inline_identity_fails_closed(
    monkeypatch, candidate_index: int, field: str, mutation: str
) -> None:
    seed = _seed()
    # Start from consistent identities so each case isolates the selected defect.
    for candidate in seed["candidates"]:
        frozen = freeze_predeclaration(resolve_candidate_predeclaration(seed, candidate))
        for identity in ("scientific_design_sha256", "strategy_behavior_sha256", "contract_sha256"):
            candidate[identity] = frozen[identity]
    candidate = seed["candidates"][candidate_index]
    if mutation == "missing":
        candidate.pop(field)
    else:
        candidate[field] = "0" * 64
    load_json = admission._load_json
    monkeypatch.setattr(admission, "_load_json", lambda path: seed if path == admission._SEED_PATH else load_json(path))
    receipt_path = SEED_PATH.with_name("strategy_factory_cohort_001_canonical_admission.json")
    qualification = json.loads(receipt_path.read_text())["selection_dataset_qualification"]
    monkeypatch.setattr(admission, "_qualify_common_selection_dataset", lambda _: qualification)

    with pytest.raises(RuntimeError, match=f"{candidate['fingerprint_id']}.*{field}"):
        build_canonical_admission_receipt()


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


def test_cohort_001_noncarry_perpetual_cost_contract_is_adverse_and_deterministic() -> None:
    seed = _seed()
    common_cost = seed["common_ohlcv_contract"]["cost_model"]
    assert common_cost["adverse_funding_allowance_bps_per_trade"] == 4.0
    assert "funding_bps_per_day" not in common_cost

    receipt = build_canonical_admission_receipt()
    cost = receipt["stage1_cost_contract"]
    assert cost["semantics"] == "adverse_per_completed_trade_allowance"
    assert cost["fees_bps"] == 12.0
    assert cost["spread_bps"] == 2.0
    assert cost["slippage_bps"] == 6.0
    assert cost["adverse_funding_allowance_bps_per_trade"] == 4.0
    assert cost["stress_totals_bps"] == {"1x": 24.0, "2x": 48.0, "3x": 72.0}
    assert cost["authenticated_realized_funding_evidence"] is False
    assert cost["deeper_validation_requires_pit_funding"] is True

    delta = next(candidate for candidate in seed["candidates"] if candidate["fingerprint_id"] == "DISC-DELTA-CARRY-001-v1")
    assert delta["cost_model"]["funding_bps_per_day"] == 0.0
    assert "adverse_funding_allowance_bps_per_trade" not in delta["cost_model"]


def test_cohort_001_zero_or_omitted_adverse_funding_fails_closed() -> None:
    seed = _seed()
    candidate = next(candidate for candidate in seed["candidates"] if candidate["fingerprint_id"] == "DISC-SIGNED-VOLUME-DRIFT-001-v1")
    resolved = resolve_candidate_predeclaration(seed, candidate)

    omitted = json.loads(json.dumps(resolved))
    omitted["cost_model"].pop("adverse_funding_allowance_bps_per_trade")
    try:
        freeze_predeclaration(omitted)
    except RuntimeError:
        pass
    else:
        raise AssertionError("omitted adverse funding allowance must fail closed")

    zero = json.loads(json.dumps(resolved))
    zero["cost_model"]["adverse_funding_allowance_bps_per_trade"] = 0.0
    try:
        freeze_predeclaration(zero)
    except RuntimeError:
        pass
    else:
        raise AssertionError("zero adverse funding allowance must fail closed")


@pytest.mark.parametrize('mutation', ('ninth_held', 'missing_candidate', 'duplicate_readiness', 'missing_readiness'))
def test_public_admission_rejects_malformed_family_membership(monkeypatch, mutation):
    seed = _seed()
    readiness = json.loads(admission._READINESS_PATH.read_text())
    if mutation == 'ninth_held':
        extra = json.loads(json.dumps(seed['candidates'][0]))
        extra['signal_rules']['warmup_hours'] += 1
        frozen = freeze_predeclaration(resolve_candidate_predeclaration(seed, extra))
        for key in ('scientific_design_sha256', 'strategy_behavior_sha256', 'contract_sha256'):
            extra[key] = frozen[key]
            assert extra[key] != seed['candidates'][0][key]
        seed['candidates'].append(extra)
    elif mutation == 'missing_candidate':
        seed['candidates'].pop(0)
    elif mutation == 'duplicate_readiness':
        readiness['candidates'].append(dict(readiness['candidates'][0]))
    else:
        readiness['candidates'].pop(0)
    original = admission._load_json
    monkeypatch.setattr(admission, '_load_json', lambda path: seed if path == admission._SEED_PATH else readiness if path == admission._READINESS_PATH else original(path))
    with pytest.raises(RuntimeError, match='membership'):
        build_canonical_admission_receipt()


@pytest.mark.parametrize('mutation', ('duplicate_member', 'missing_member', 'different_member', 'wrong_count', 'wrong_family', 'different_readiness_member'))
def test_public_admission_reconciles_frozen_multiplicity_membership(monkeypatch, mutation):
    multiplicity = json.loads(admission._MULTIPLICITY_PATH.read_text())
    readiness = json.loads(admission._READINESS_PATH.read_text())
    family = multiplicity['family']
    if mutation == 'duplicate_member':
        family['members'][1] = family['members'][0]
    elif mutation == 'missing_member':
        family['members'].pop()
    elif mutation == 'different_member':
        family['members'][0] = 'UNDECLARED-v1'
    elif mutation == 'wrong_count':
        family['planned_hypothesis_count'] = 9
    elif mutation == 'wrong_family':
        family['family_id'] = 'UNDECLARED-FAMILY'
    else:
        readiness['candidates'][0]['fingerprint_id'] = 'UNDECLARED-v1'
    original = admission._load_json
    monkeypatch.setattr(admission, '_load_json', lambda path: multiplicity if path == admission._MULTIPLICITY_PATH else readiness if path == admission._READINESS_PATH else original(path))
    def forbidden_qualification(_):
        pytest.fail('malformed membership reached dataset qualification')
    monkeypatch.setattr(admission, '_qualify_common_selection_dataset', forbidden_qualification)
    with pytest.raises(RuntimeError, match='membership'):
        build_canonical_admission_receipt()

@pytest.mark.parametrize(
    "raw",
    (
        '{"protected": 1, "protected": 2}',
        '{"protected": NaN}',
        '{"protected": Infinity}',
        '{"protected": -Infinity}',
    ),
)
def test_admission_json_loader_rejects_ambiguous_or_nonstandard_json(
    tmp_path: Path, raw: str
) -> None:
    path = tmp_path / "protected.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(RuntimeError):
        admission._load_json(path)


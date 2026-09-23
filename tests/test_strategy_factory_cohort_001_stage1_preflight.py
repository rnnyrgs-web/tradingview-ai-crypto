from __future__ import annotations

import json

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_stage1_preflight import (
    EXPECTED_BLOCKED_CANDIDATE,
    POWER_ARTIFACT_PATH,
    assert_economic_outcome_read_allowed,
    executable_candidate_ids,
    load_power_feasibility,
)
from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import CANDIDATE_IDS


EXPECTED_EXECUTABLE = (
    "DISC-RESIDUAL-REV-001-v1",
    "DISC-SIGNED-VOLUME-DRIFT-001-v1",
    "DISC-LOWVOL-DRIFT-REV-001-v1",
    "DISC-MODERATEVOL-AUTOCORR-001-v1",
    "DISC-RANGE-AUCTION-REV-001-v1",
)


def test_preflight_authenticates_power_artifact_and_returns_exact_five_ids() -> None:
    payload = load_power_feasibility()
    assert payload["candidate"]["fingerprint_id"] == EXPECTED_BLOCKED_CANDIDATE
    assert payload["candidate"]["maximum_possible_validation_independent_events"] == 18
    assert payload["candidate"]["minimum_independent_events_validation"] == 20
    assert payload["deterministic_conclusion"]["economic_evidence"] == "NONE_OPENED"
    assert tuple(executable_candidate_ids()) == EXPECTED_EXECUTABLE
    assert set(EXPECTED_EXECUTABLE) == set(CANDIDATE_IDS) - {EXPECTED_BLOCKED_CANDIDATE}


def test_weekend_candidate_is_blocked_before_any_economic_outcome_read() -> None:
    with pytest.raises(RuntimeError, match="INCONCLUSIVE_POWER_PRE_OUTCOME"):
        assert_economic_outcome_read_allowed(EXPECTED_BLOCKED_CANDIDATE)


@pytest.mark.parametrize("candidate_id", EXPECTED_EXECUTABLE)
def test_power_overlay_does_not_grant_or_block_other_candidates(candidate_id: str) -> None:
    # Returning means only that this one structural-power veto does not apply.
    # It is not canonical Stage-1 authority and does not bypass any other gate.
    assert assert_economic_outcome_read_allowed(candidate_id) is None


def test_unknown_candidate_fails_closed() -> None:
    with pytest.raises(ValueError, match="not Cohort-001 admitted"):
        assert_economic_outcome_read_allowed("DISC-NOT-ADMITTED-v1")


def test_tampered_artifact_digest_fails_closed(monkeypatch, tmp_path) -> None:
    payload = json.loads(POWER_ARTIFACT_PATH.read_text(encoding="utf-8"))
    payload["candidate"]["maximum_possible_validation_independent_events"] = 20
    tampered = tmp_path / "power.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    import orchestration.cohorts.strategy_factory_cohort_001_stage1_preflight as preflight

    monkeypatch.setattr(preflight, "POWER_ARTIFACT_PATH", tampered)
    with pytest.raises(RuntimeError, match="digest mismatch"):
        preflight.load_power_feasibility()


@pytest.mark.parametrize(
    ("source_key", "error_match"),
    (
        ("stage1_runner_blob_sha", "runner source blob mismatch"),
        ("stage1_execution_contract_blob_sha", "execution source blob mismatch"),
    ),
)
def test_valid_self_digest_cannot_hide_source_blob_drift(
    monkeypatch,
    tmp_path,
    source_key: str,
    error_match: str,
) -> None:
    import orchestration.cohorts.strategy_factory_cohort_001_stage1_preflight as preflight

    payload = json.loads(POWER_ARTIFACT_PATH.read_text(encoding="utf-8"))
    payload["source_contracts"][source_key] = "0" * 40
    payload["artifact_sha256"] = preflight._canonical_sha256(payload)
    tampered = tmp_path / f"{source_key}.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(preflight, "POWER_ARTIFACT_PATH", tampered)
    with pytest.raises(RuntimeError, match=error_match):
        preflight.load_power_feasibility()


def test_valid_self_digest_cannot_hide_validation_minimum_drift(monkeypatch, tmp_path) -> None:
    import orchestration.cohorts.strategy_factory_cohort_001_stage1_preflight as preflight

    payload = json.loads(POWER_ARTIFACT_PATH.read_text(encoding="utf-8"))
    # Keep the structural inequality true (18 < 19) so the source-contract gate,
    # rather than the already-existing arithmetic guard, must catch the drift.
    payload["candidate"]["minimum_independent_events_validation"] = 19
    payload["artifact_sha256"] = preflight._canonical_sha256(payload)
    tampered = tmp_path / "minimum-drift.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(preflight, "POWER_ARTIFACT_PATH", tampered)
    with pytest.raises(RuntimeError, match="validation minimum diverges"):
        preflight.load_power_feasibility()

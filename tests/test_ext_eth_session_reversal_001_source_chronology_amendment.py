from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT_PATH = ROOT / "orchestration/external_replication/ext_eth_session_reversal_001_v1.json"
AMENDMENT_PATH = (
    ROOT
    / "orchestration/external_replication/"
    "ext_eth_session_reversal_001_source_chronology_amendment_v1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _self_digest(document: dict) -> str:
    payload = dict(document)
    payload.pop("artifact_sha256")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_chronology_amendment_is_self_digested_and_parent_bound() -> None:
    parent = _load(PARENT_PATH)
    amendment = _load(AMENDMENT_PATH)

    assert amendment["artifact_sha256"] == _self_digest(amendment)
    assert amendment["artifact_sha256"] == (
        "17d17c81790b40225d886972369d4cac601c20286ce06eecafba4f5b31094722"
    )
    assert amendment["parent_replication_id"] == parent["replication_id"]
    assert amendment["parent_artifact_sha256"] == parent["artifact_sha256"]
    assert amendment["parent_contract_git_blob_sha"] == (
        "e27a19904130ceb0dcaff670b0eecb93b550103e"
    )
    assert amendment["formed_before_stage1_outcomes"] is True


def test_public_source_freeze_is_not_proven_before_h1() -> None:
    amendment = _load(AMENDMENT_PATH)
    source = amendment["observed_source_provenance"]

    h1_end = _utc("2026-06-30T23:59:59Z")
    repo_created = _utc(source["repository_created_at_utc"])
    code_commit = _utc(source["replication_code_first_public_commit_at_utc"])
    pinned_commit = _utc(source["pinned_replication_commit_at_utc"])

    assert source["source_repository"] == "wzf01195010-png/Crypto-day-night-effects"
    assert source["replication_code_first_public_commit_sha"] == (
        "540574518f46fb0fbf71aa8d91aaf3995d814b29"
    )
    assert source["pinned_replication_commit_sha"] == (
        "5693993e108f2b3668bd21b1dd36ae31f79d8fcd"
    )
    assert repo_created > h1_end
    assert code_commit > h1_end
    assert pinned_commit > h1_end
    assert source["source_data_sample_end_utc"] == "2025-12-31T23:00:00Z"
    assert source["pre_h1_strategy_freeze_proven"] is False
    assert "absence-of-proof" in source["reason"]
    assert "not a claim that the authors used 2026H1 outcomes" in source["reason"]


def test_h1_positive_result_cannot_mint_independent_replication_or_promotion() -> None:
    amendment = _load(AMENDMENT_PATH)
    evidence = amendment["evidence_reclassification"]

    assert evidence["new_label"] == (
        "RETROSPECTIVE_PROJECT_UNREAD_SOURCE_CHRONOLOGY_UNPROVEN"
    )
    assert evidence["project_outcome_unread_before_predeclaration"] is True
    assert evidence["source_independent_of_h1_outcomes_proven"] is False
    assert evidence["independent_replication_claim_allowed_from_h1"] is False
    assert evidence["profitability_claim_allowed_from_h1"] is False
    assert evidence["deep_candidate_promotion_allowed_from_h1_alone"] is False
    assert evidence["positive_h1_result_authority"] == (
        "HYPOTHESIS_PRESERVATION_AND_RETROSPECTIVE_DIAGNOSTICS_ONLY"
    )
    assert evidence["negative_h1_result_authority"] == (
        "FALSIFICATION_ALLOWED_UNDER_PROJECT_FROZEN_RULES"
    )
    assert evidence["strong_positive_evidence_requires_one_of"] == [
        "AUTHENTICATED_SOURCE_FREEZE_BEFORE_2026-01-02",
        "GENUINE_FORWARD_POST_PROJECT_FORMATION_EVIDENCE",
    ]


def test_genuine_forward_and_safety_locks_remain_unchanged() -> None:
    amendment = _load(AMENDMENT_PATH)
    forward = amendment["genuine_forward_binding"]
    locks = amendment["authority_locks"]
    learning = amendment["failure_learning"]

    assert forward["start_utc"] == "2026-09-24T17:00:00Z"
    assert forward["first_complete_trading_date"] == "2026-09-25"
    assert forward["shadow_must_remain_immutable_and_research_only"] is True
    assert forward["tuning_from_shadow_forbidden"] is True
    assert forward["broker_connected"] is False
    assert forward["live_trading"] is False
    assert forward["promotion_authority"] is False

    assert learning["classification"] == "PRE_OUTCOME_EXTERNAL_SOURCE_CHRONOLOGY_GAP"
    assert learning["economic_negative_evidence"] is False
    assert learning["family_priority_reduction_from_this_gap"] is False
    assert learning["rejected_memory_write_from_this_gap"] is False

    assert locks == {
        "stage1_started": False,
        "stage1_pnl_opened": False,
        "retrospective_holdout_opened": False,
        "genuine_forward_shadow_opened": False,
        "protected_oos_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
    }

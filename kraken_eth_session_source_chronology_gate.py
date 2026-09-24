"""Fail-closed authority gate for trusted Kraken ETH-session acquisition.

This gate binds the acquisition lane to the append-only source-chronology amendment
for EXT-ETH-SESSION-REVERSAL-001-v1 before any provider bytes are fetched. It grants
no data, screening, profitability, promotion, broker, or trading authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = "orchestration/external_replication/ext_eth_session_reversal_001_v1.json"
CONTRACT_ID = "EXT-ETH-SESSION-REVERSAL-001-v1"
CONTRACT_ARTIFACT_SHA256 = "fee604ea0e2f993cd109cadcc6717deedbb7bd02e044cf380de2ef80e91afcc3"
CONTRACT_GIT_BLOB_SHA = "e27a19904130ceb0dcaff670b0eecb93b550103e"
AMENDMENT_PATH = (
    "orchestration/external_replication/"
    "ext_eth_session_reversal_001_source_chronology_amendment_v1.json"
)
AMENDMENT_ID = "EXT-ETH-SESSION-REVERSAL-001-v1-SOURCE-CHRONOLOGY-v1"
AMENDMENT_ARTIFACT_SHA256 = "17d17c81790b40225d886972369d4cac601c20286ce06eecafba4f5b31094722"
H1_EVIDENCE_LABEL = "RETROSPECTIVE_PROJECT_UNREAD_SOURCE_CHRONOLOGY_UNPROVEN"
FORWARD_START_UTC = "2026-09-24T17:00:00Z"
FORWARD_FIRST_COMPLETE_DATE = "2026-09-25"


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"duplicate JSON object key: {key}")
        parsed[key] = value
    return parsed


def _reject_nonstandard_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _strict_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} rejected: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object")
    return payload


def _artifact_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _read(root: Path, relative_path: str) -> bytes:
    return (root / relative_path).resolve().read_bytes()


def validate_source_chronology_binding(
    repo_root: str | Path | None = None,
) -> dict[str, str | bool]:
    root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parent
    contract_raw = _read(root, CONTRACT_PATH)
    amendment_raw = _read(root, AMENDMENT_PATH)
    contract = _strict_json(contract_raw, label="ETH session replication contract")
    amendment = _strict_json(amendment_raw, label="ETH source chronology amendment")

    if contract.get("replication_id") != CONTRACT_ID:
        raise ValueError("ETH session replication contract identity mismatch")
    if contract.get("artifact_sha256") != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("ETH session replication artifact identity mismatch")
    if _artifact_digest(contract) != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("ETH session replication artifact self-digest mismatch")
    if _git_blob_sha(contract_raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("ETH session replication exact Git blob identity mismatch")

    if amendment.get("amendment_id") != AMENDMENT_ID:
        raise ValueError("source chronology amendment identity mismatch")
    if amendment.get("artifact_sha256") != AMENDMENT_ARTIFACT_SHA256:
        raise ValueError("source chronology amendment artifact identity mismatch")
    if _artifact_digest(amendment) != AMENDMENT_ARTIFACT_SHA256:
        raise ValueError("source chronology amendment self-digest mismatch")
    if amendment.get("parent_replication_id") != CONTRACT_ID:
        raise ValueError("source chronology amendment parent ID mismatch")
    if amendment.get("parent_artifact_sha256") != CONTRACT_ARTIFACT_SHA256:
        raise ValueError("source chronology amendment parent artifact mismatch")
    if amendment.get("parent_contract_git_blob_sha") != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("source chronology amendment parent blob mismatch")
    if amendment.get("formed_before_stage1_outcomes") is not True:
        raise ValueError("source chronology amendment was not frozen pre-outcome")

    source = amendment.get("observed_source_provenance")
    evidence = amendment.get("evidence_reclassification")
    forward = amendment.get("genuine_forward_binding")
    locks = amendment.get("authority_locks")
    learning = amendment.get("failure_learning")
    if not all(isinstance(block, dict) for block in (source, evidence, forward, locks, learning)):
        raise ValueError("source chronology amendment authority blocks missing")

    if source.get("pre_h1_strategy_freeze_proven") is not False:
        raise ValueError("pre-H1 source-freeze classification changed")
    if evidence.get("new_label") != H1_EVIDENCE_LABEL:
        raise ValueError("retrospective H1 evidence classification changed")
    if evidence.get("source_independent_of_h1_outcomes_proven") is not False:
        raise ValueError("H1 source-independence classification changed")
    if evidence.get("independent_replication_claim_allowed_from_h1") is not False:
        raise ValueError("retrospective H1 cannot grant independent-replication authority")
    if evidence.get("profitability_claim_allowed_from_h1") is not False:
        raise ValueError("retrospective H1 cannot grant profitability authority")
    if evidence.get("deep_candidate_promotion_allowed_from_h1_alone") is not False:
        raise ValueError("retrospective H1 cannot grant deep-promotion authority")
    if evidence.get("negative_h1_result_authority") != (
        "FALSIFICATION_ALLOWED_UNDER_PROJECT_FROZEN_RULES"
    ):
        raise ValueError("negative H1 falsification authority changed")

    if forward.get("start_utc") != FORWARD_START_UTC:
        raise ValueError("genuine-forward start changed")
    if forward.get("first_complete_trading_date") != FORWARD_FIRST_COMPLETE_DATE:
        raise ValueError("genuine-forward first complete date changed")
    if forward.get("shadow_must_remain_immutable_and_research_only") is not True:
        raise ValueError("genuine-forward shadow research-only lock changed")
    if forward.get("tuning_from_shadow_forbidden") is not True:
        raise ValueError("shadow tuning lock changed")
    if any(forward.get(key) is not False for key in ("broker_connected", "live_trading", "promotion_authority")):
        raise ValueError("genuine-forward broker/live/promotion locks changed")

    expected_locks = {
        "stage1_started": False,
        "stage1_pnl_opened": False,
        "retrospective_holdout_opened": False,
        "genuine_forward_shadow_opened": False,
        "protected_oos_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    if locks != expected_locks:
        raise ValueError("source chronology authority locks changed")
    if learning.get("economic_negative_evidence") is not False:
        raise ValueError("chronology gap cannot be reclassified as economic failure")
    if learning.get("rejected_memory_write_from_this_gap") is not False:
        raise ValueError("chronology gap cannot write rejected strategy memory")

    return {
        "status": "SOURCE_CHRONOLOGY_BOUND_PRE_PROVIDER_FETCH",
        "contract_id": CONTRACT_ID,
        "contract_artifact_sha256": CONTRACT_ARTIFACT_SHA256,
        "contract_bytes_sha256": hashlib.sha256(contract_raw).hexdigest(),
        "amendment_id": AMENDMENT_ID,
        "amendment_artifact_sha256": AMENDMENT_ARTIFACT_SHA256,
        "amendment_bytes_sha256": hashlib.sha256(amendment_raw).hexdigest(),
        "retrospective_h1_evidence_classification": H1_EVIDENCE_LABEL,
        "independent_replication_authority": False,
        "profitability_claim_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
    }


def main() -> int:
    print(json.dumps(validate_source_chronology_binding(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

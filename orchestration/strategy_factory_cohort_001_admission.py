from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from orchestration.strategy_predeclaration import freeze_predeclaration
from strategy_dataset_preflight import qualify_cohort001_dataset

_ROOT = Path(__file__).resolve().parent
_SEED_PATH = _ROOT / "cohorts" / "strategy_factory_cohort_001_seed.json"
_READINESS_PATH = _ROOT / "cohorts" / "strategy_factory_cohort_001_readiness.json"
_OWNERSHIP_PATH = _ROOT / "cohorts" / "strategy_factory_cohort_001_ownership_correction.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def resolve_candidate_predeclaration(
    seed: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Resolve one Cohort-001 seed into the canonical #507 predeclaration shape.

    The legacy seed intentionally contains stale inline digests. They are never
    copied here. Canonical identities are recomputed only by freeze_predeclaration.
    This function performs no market-data read and no outcome calculation.
    """
    common = seed.get("common_ohlcv_contract")
    if not isinstance(common, dict):
        raise RuntimeError("Cohort-001 seed is missing common_ohlcv_contract")
    if not isinstance(candidate, dict):
        raise RuntimeError("Cohort-001 candidate must be an object")

    required_candidate = (
        "hypothesis_id",
        "fingerprint_id",
        "family",
        "economic_mechanism",
        "hypothesis",
        "signal_rules",
        "execution_rules",
    )
    missing = [key for key in required_candidate if key not in candidate]
    if missing:
        raise RuntimeError(f"Cohort-001 candidate missing fields: {missing}")

    return {
        "schema_version": 1,
        "hypothesis_id": candidate["hypothesis_id"],
        "fingerprint_id": candidate["fingerprint_id"],
        "family": candidate["family"],
        "economic_mechanism": candidate["economic_mechanism"],
        "hypothesis": candidate["hypothesis"],
        "target_markets": candidate.get("target_markets", common["target_markets"]),
        "target_timeframes": candidate.get("target_timeframes", common["target_timeframes"]),
        "formation_cutoff": candidate.get("formation_cutoff", common["formation_cutoff"]),
        "data_contract": candidate.get("data_contract", common["data_contract"]),
        "signal_rules": candidate["signal_rules"],
        "execution_rules": candidate["execution_rules"],
        "cost_model": candidate.get("cost_model", common["cost_model"]),
        "search_plan": candidate.get("search_plan", common["search_plan"]),
        "validation_plan": candidate.get("validation_plan", common["validation_plan"]),
        "protected_evidence": candidate.get(
            "protected_evidence", common["protected_evidence"]
        ),
    }


def _qualify_common_selection_dataset(seed: dict[str, Any]) -> dict[str, Any]:
    """Bind #528's protected-safe source qualification before screen authority.

    The qualifier authenticates immutable compressed bytes, decodes market values
    only through 2026-08-31 23:00 UTC, and inspects protected rows by timestamp only.
    It computes no strategy signals, labels, returns, P&L, or other economic outcomes.
    """
    common = seed.get("common_ohlcv_contract")
    if not isinstance(common, dict):
        raise RuntimeError("Cohort-001 seed is missing common_ohlcv_contract")
    data_contract = common.get("data_contract")
    if not isinstance(data_contract, dict):
        raise RuntimeError("Cohort-001 common data contract is missing")

    receipt = qualify_cohort001_dataset()
    if receipt.get("status") != "QUALIFIED_DEVELOPMENT_ONLY":
        raise RuntimeError("Cohort-001 dataset did not qualify development-only")
    if receipt.get("economic_outcomes_computed") is not False:
        raise RuntimeError("dataset qualification must remain outcome-blind")
    if receipt.get("strategy_signals_computed") is not False:
        raise RuntimeError("dataset qualification must not compute strategy signals")
    if receipt.get("untouched_oos_opened") is not False:
        raise RuntimeError("dataset qualification opened protected OOS")
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or checks.get("protected_ohlcv_json_decoded") is not False:
        raise RuntimeError("dataset qualification must leave protected OHLCV opaque")

    expected_dataset = data_contract.get("normalized_rows_sha256")
    if receipt.get("source_dataset_sha256") != expected_dataset:
        raise RuntimeError("Cohort-001 seed and #528 qualifier bind different dataset identities")
    if receipt.get("development_end_utc") != data_contract.get("selection_validation_end_utc"):
        raise RuntimeError("Cohort-001 development cutoff differs from #528 qualifier")
    if receipt.get("protected_start_utc") != data_contract.get("protected_oos_start_utc"):
        raise RuntimeError("Cohort-001 protected boundary differs from #528 qualifier")

    return {
        "qualification_id": receipt["qualification_id"],
        "status": receipt["status"],
        "source_git_blob_sha1": receipt["source_git_blob_sha1"],
        "source_dataset_sha256": receipt["source_dataset_sha256"],
        "development_end_utc": receipt["development_end_utc"],
        "protected_start_utc": receipt["protected_start_utc"],
        "development_timestamp_identity_sha256": receipt[
            "development_timestamp_identity_sha256"
        ],
        "development_rows_total": receipt["development_rows_total"],
        "protected_rows_excluded_total": receipt["protected_rows_excluded_total"],
        "protected_ohlcv_json_decoded": False,
        "economic_outcomes_computed": False,
        "strategy_signals_computed": False,
        "receipt_sha256": receipt["receipt_sha256"],
    }


def build_canonical_admission_receipt() -> dict[str, Any]:
    """Canonically admit Cohort-001 and bind protected-safe data readiness.

    Result status is an execution/readiness decision only. Passing admission is
    not profitability evidence and grants no OOS, forward, broker or trade authority.
    """
    seed = _load_json(_SEED_PATH)
    readiness = _load_json(_READINESS_PATH)
    ownership = _load_json(_OWNERSHIP_PATH)
    selection_dataset = _qualify_common_selection_dataset(seed)

    readiness_by_id = {
        row["fingerprint_id"]: row["readiness"]
        for row in readiness.get("candidates", [])
        if isinstance(row, dict)
        and isinstance(row.get("fingerprint_id"), str)
        and isinstance(row.get("readiness"), str)
    }
    affected = ownership.get("affected_seed", {})
    held_fingerprint = affected.get("fingerprint_id") if isinstance(affected, dict) else None

    candidates = seed.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Cohort-001 seed must contain candidates")

    rows: list[dict[str, Any]] = []
    behavior_owner: dict[str, str] = {}
    contract_owner: dict[str, str] = {}

    for candidate in candidates:
        resolved = resolve_candidate_predeclaration(seed, candidate)
        fingerprint = resolved["fingerprint_id"]
        try:
            frozen = freeze_predeclaration(resolved)
        except RuntimeError as exc:
            rows.append(
                {
                    "fingerprint_id": fingerprint,
                    "status": "REJECTED_CANONICAL_ADMISSION",
                    "reason": str(exc),
                    "screening_authority": False,
                }
            )
            continue

        behavior_digest = frozen["strategy_behavior_sha256"]
        prior_behavior = behavior_owner.get(behavior_digest)
        if prior_behavior is not None:
            raise RuntimeError(
                "Cohort-001 contains duplicate executable behavior: "
                f"{prior_behavior} and {fingerprint}"
            )
        behavior_owner[behavior_digest] = fingerprint

        contract_digest = frozen["contract_sha256"]
        prior_contract = contract_owner.get(contract_digest)
        if prior_contract is not None:
            raise RuntimeError(
                f"Cohort-001 duplicate frozen contract: {prior_contract} and {fingerprint}"
            )
        contract_owner[contract_digest] = fingerprint

        readiness_state = readiness_by_id.get(fingerprint)
        if fingerprint == held_fingerprint:
            status = "HOLD_ACTIVE_OWNERSHIP_COLLISION"
            screening_authority = False
        elif readiness_state == "BLOCKED_DATA_PREFLIGHT":
            status = "DATA_BLOCKED"
            screening_authority = False
        elif readiness_state and "POWER_RISK" in readiness_state:
            status = "ADMITTED_DATA_QUALIFIED_POWER_RISK"
            screening_authority = True
        elif readiness_state == "READY_FOR_SCHEMA_PREFLIGHT_AFTER_507":
            status = "ADMITTED_DATA_QUALIFIED"
            screening_authority = True
        else:
            raise RuntimeError(
                f"Cohort-001 candidate {fingerprint} has unknown readiness {readiness_state!r}"
            )

        rows.append(
            {
                "fingerprint_id": fingerprint,
                "status": status,
                "scientific_design_sha256": frozen["scientific_design_sha256"],
                "strategy_behavior_sha256": frozen["strategy_behavior_sha256"],
                "contract_sha256": frozen["contract_sha256"],
                "screening_authority": screening_authority,
                "selection_dataset_receipt_sha256": selection_dataset["receipt_sha256"]
                if screening_authority
                else None,
                "untouched_oos_opened": False,
                "genuine_forward_opened": False,
                "broker_connected": False,
                "trade_authority": False,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 2,
        "artifact_type": "strategy_factory_cohort_001_canonical_admission_receipt",
        "cohort_id": seed.get("cohort_id"),
        "multiple_testing_family_id": seed.get("multiple_testing", {}).get("family_id"),
        "planned_hypothesis_count": seed.get("multiple_testing", {}).get(
            "planned_hypothesis_count"
        ),
        "canonical_identity_source": "orchestration.strategy_predeclaration.freeze_predeclaration",
        "selection_dataset_qualification": selection_dataset,
        "outcomes_read": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "deep_candidate_promoted": False,
        "broker_connected": False,
        "trade_authority": False,
        "candidates": rows,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> None:
    print(json.dumps(build_canonical_admission_receipt(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

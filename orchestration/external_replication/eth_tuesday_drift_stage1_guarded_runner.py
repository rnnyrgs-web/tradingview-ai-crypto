from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping

from orchestration.external_replication import eth_tuesday_drift_runner as base

ROOT = Path(__file__).resolve().parents[2]
RISK_AMENDMENT_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_stage1_risk_amendment.json"
)

REPLICATION_ID = base.REPLICATION_ID
PARENT_ARTIFACT_SHA256 = base.PARENT_ARTIFACT_SHA256
BASE_EXECUTION_CONTRACT_SHA256 = "823d7bbfbd411056358721dfb1e7f3764c7a445306f62aaa156945a6cd2ca46c"
PRIMARY_COST_BPS = base.PRIMARY_COST_BPS
TAIL_POSITIVE_POOL_FRACTION = 0.50


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_and_validate_risk_amendment(path: Path = RISK_AMENDMENT_PATH) -> dict:
    amendment = json.loads(path.read_text(encoding="utf-8"))
    supplied = amendment.pop("artifact_sha256", None)
    if not isinstance(supplied, str):
        raise RuntimeError("risk amendment artifact_sha256 missing")
    actual = hashlib.sha256(_canonical_json(amendment)).hexdigest()
    if actual != supplied:
        raise RuntimeError("risk amendment artifact_sha256 mismatch")
    amendment["artifact_sha256"] = supplied

    if amendment.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("risk amendment replication mismatch")
    if amendment.get("parent_artifact_sha256") != PARENT_ARTIFACT_SHA256:
        raise RuntimeError("risk amendment parent mismatch")
    if amendment.get("base_execution_contract_sha256") != BASE_EXECUTION_CONTRACT_SHA256:
        raise RuntimeError("risk amendment execution-contract mismatch")
    if amendment.get("formed_pre_outcome") is not True:
        raise RuntimeError("risk amendment must be frozen pre-outcome")
    if amendment.get("outcomes_read_to_form_amendment") is not False:
        raise RuntimeError("risk amendment outcome chronology drift")

    locks = amendment.get("authority_locks", {})
    if any(
        locks.get(key) is not False
        for key in (
            "base_runner_survivor_authority_without_overlay",
            "baseline_pnl_opened",
            "protected_oos_opened",
            "genuine_forward_opened",
            "profitability_claim_allowed",
            "promotion_authority",
            "broker_connected",
            "trade_authority",
        )
    ):
        raise RuntimeError("risk amendment authority lock drift")
    return amendment


def _risk_metrics(sessions: Iterable[base.TuesdaySession]) -> dict:
    net = [session.gross_bps - PRIMARY_COST_BPS for session in sessions]
    positives = [value for value in net if value > 0]
    losses = [value for value in net if value < 0]
    positive_pool = sum(positives)
    worst_loss_abs = abs(min(losses)) if losses else 0.0
    tail_limit = TAIL_POSITIVE_POOL_FRACTION * positive_pool
    catastrophic_tail_pass = positive_pool > 0 and worst_loss_abs <= tail_limit

    without_best_mean = None
    single_winner_dependence_pass = False
    if len(net) >= 2:
        best_index = max(range(len(net)), key=net.__getitem__)
        without_best = net[:best_index] + net[best_index + 1 :]
        without_best_mean = mean(without_best)
        single_winner_dependence_pass = without_best_mean > 0

    return {
        "sessions": len(net),
        "positive_net_pool_bps": positive_pool,
        "worst_net_loss_abs_bps": worst_loss_abs,
        "catastrophic_tail_limit_bps": tail_limit,
        "catastrophic_tail_pass": catastrophic_tail_pass,
        "without_best_mean_net_bps": without_best_mean,
        "single_winner_dependence_pass": single_winner_dependence_pass,
    }


def evaluate_stage1_guarded(rows: Iterable[Mapping[str, object]]) -> dict:
    frozen_rows = tuple(rows)
    result = base.evaluate_stage1(frozen_rows)
    sessions, _ = base.build_frozen_schedule(frozen_rows)
    half_1 = [session for session in sessions if session.half == "half_1"]
    half_2 = [session for session in sessions if session.half == "half_2"]

    risk = {
        "full": _risk_metrics(sessions),
        "half_1": _risk_metrics(half_1),
        "half_2": _risk_metrics(half_2),
    }
    tail_ok = risk["half_1"]["catastrophic_tail_pass"] and risk["half_2"]["catastrophic_tail_pass"]
    single_winner_ok = (
        risk["half_1"]["single_winner_dependence_pass"]
        and risk["half_2"]["single_winner_dependence_pass"]
    )

    result["risk_amendment"] = {
        "primary_cost_bps": PRIMARY_COST_BPS,
        "tail_positive_pool_fraction": TAIL_POSITIVE_POOL_FRACTION,
        "metrics": risk,
        "authority": "PRE_OUTCOME_PROJECT_RISK_OVERLAY",
    }
    result["gates"]["catastrophic_tail_veto_48bps_both_halves"] = tail_ok
    result["gates"]["single_winner_dependence_veto_48bps_both_halves"] = single_winner_ok

    if not tail_ok or not single_winner_ok:
        result["survived_stage1_economic_gates"] = False
        categories = set(result.get("failure_categories") or [])
        if result.get("failure_classification"):
            categories.add(str(result["failure_classification"]))
        categories.add("CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION")
        result["failure_categories"] = sorted(categories)
        # Observed catastrophic-tail / single-winner dependence is a rejecting
        # risk fact even when the remaining sample is otherwise underpowered.
        if result["status"] in {"STAGE1_SURVIVOR_ONLY", "INCONCLUSIVE_POWER"}:
            result["status"] = "REJECT_PRE_OOS"
            result["failure_classification"] = "CATASTROPHIC_TAIL_OR_WINNER_CONCENTRATION"
    else:
        categories = set(result.get("failure_categories") or [])
        if result.get("failure_classification"):
            categories.add(str(result["failure_classification"]))
        result["failure_categories"] = sorted(categories)

    return result


def run_canonical_stage1_guarded() -> dict:
    """Run the exact frozen Stage-1 path with the append-only risk overlay.

    Independent exact-head review/integration remains external authority. This
    function cannot mint Stage-2, profitability, promotion, broker or trade authority.
    """
    base.load_and_validate_contracts()
    load_and_validate_risk_amendment()
    rows = base.load_frozen_eth_rows()
    result = evaluate_stage1_guarded(rows)
    result["evidence_authority"] = "FROZEN_DATASET_VERIFIED_REVIEW_AUTHORITY_EXTERNAL_RISK_OVERLAY"
    result["authority"]["stage2_baseline_execution_allowed"] = False
    result["authority"]["profitability_claim_allowed"] = False
    result["authority"]["deep_promotion_allowed"] = False
    return result

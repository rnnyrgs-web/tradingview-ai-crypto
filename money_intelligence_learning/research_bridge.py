"""Emit frozen, provenance-bound hypotheses; never trade or auto-promote."""

from __future__ import annotations

from copy import deepcopy

from orchestration.rejected_fingerprints import is_rejected_fingerprint
from profitability_learning.contracts import fingerprint
from research_director import build_mission, rank_missions


ELIGIBLE = {"PROMISING", "SUPPORTED"}


def emit_research_hypotheses(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("research_only") is not True:
        raise ValueError("validated research-only Money Intelligence snapshot required")
    hypotheses = []
    for mechanism_id, row in sorted((snapshot.get("mechanisms") or {}).items()):
        contract, state = row.get("contract"), row.get("state")
        if not isinstance(contract, dict) or not isinstance(state, dict) or state.get("status") not in ELIGIBLE:
            continue
        for lane in contract["downstream_lanes"]:
            identity = {
                "mechanism_id": mechanism_id,
                "contract_id": contract["contract_id"],
                "lane": lane,
                "causal_chain": contract["causal_chain"],
                "falsifier": contract["falsifier"],
                "evidence_ids": state["evidence_ids"],
            }
            digest = fingerprint(identity)
            prefix = "MI-BIG-MOVE" if lane == "BIG_MOVE" else "MI-STRATEGY-COMPONENT"
            candidate_fingerprint = f"{prefix}-{digest[:20]}-v1"
            if is_rejected_fingerprint(candidate_fingerprint):
                raise ValueError("downstream fingerprint collides with rejected memory")
            hypotheses.append(
                {
                    "schema_version": 1,
                    "hypothesis_id": "mi-hypothesis-" + digest[:24],
                    "fingerprint": candidate_fingerprint,
                    "lane": lane,
                    "hypothesis": contract["claim"],
                    "source_mechanism_id": mechanism_id,
                    "source_contract_id": contract["contract_id"],
                    "source_mechanism_status": state["status"],
                    "source_confidence": state["confidence"],
                    "source_evidence_ids": deepcopy(state["evidence_ids"]),
                    "causal_chain": deepcopy(contract["causal_chain"]),
                    "expected_direction": contract["expected_direction"],
                    "expected_horizon_days": contract["expected_horizon_days"],
                    "falsifier": contract["falsifier"],
                    "matched_control_design": deepcopy(contract["matched_control_design"]),
                    "regime_scope": deepcopy(contract["regime_scope"]),
                    "target_assets": deepcopy(contract["target_assets"]),
                    "search_breadth": contract["search_breadth"],
                    "status": "FROZEN_RESEARCH_HYPOTHESIS_REQUIRES_VALIDATION",
                    "research_only": True,
                    "automatic_execution_authority": False,
                    "strategy_mutation_authority": False,
                    "trade_authority": False,
                    "promotion_authority": False,
                    "untouched_oos_authority": False,
                }
            )
    return hypotheses


def rank_research_missions(snapshot):
    """Consume emitted hypotheses through the canonical mission scorer.

    These records are research-routing proposals only.  The bridge intentionally
    keeps automatic execution false so a frozen scientific contract and normal
    coordination ownership are still required before any experiment runs.
    """
    hypotheses = emit_research_hypotheses(snapshot)
    by_id = {}
    missions = []
    for hypothesis in hypotheses:
        lane = "big-move-intelligence" if hypothesis["lane"] == "BIG_MOVE" else "strategy-component-research"
        confidence = float(hypothesis["source_confidence"])
        mission = build_mission(
            lane=lane,
            horizon=f"{hypothesis['expected_horizon_days']}d",
            direction=hypothesis["expected_direction"],
            theme=hypothesis["source_mechanism_id"],
            hypothesis=hypothesis["hypothesis"],
            expected_information_gain=max(0.25, 1.0 - confidence),
            expected_signal_impact=0.05,
            expected_profitability_impact=0.05,
            sample_readiness=min(0.5, confidence),
            novelty=0.9,
            falsification_value=0.95,
            actionable_evidence_probability=0.2,
            compute_cost=0.2,
            experiment_id=hypothesis["hypothesis_id"],
        )
        missions.append(mission)
        by_id[mission.mission_id] = hypothesis
    output = []
    for mission in rank_missions(missions):
        source = by_id[mission.mission_id]
        output.append(
            {
                **mission.to_dict(),
                "source_hypothesis_id": source["hypothesis_id"],
                "source_hypothesis_fingerprint": source["fingerprint"],
                "source_mechanism_id": source["source_mechanism_id"],
                "source_evidence_ids": deepcopy(source["source_evidence_ids"]),
                "research_only": True,
                "automatic_execution_authority": False,
                "strategy_mutation_authority": False,
                "trade_authority": False,
                "promotion_authority": False,
            }
        )
    return output

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROPOSED_PATH = ROOT / "resource_recommendations_proposed.json"
DECISIONS_PATH = ROOT / "resource_recommendations_decisions.json"

PROPOSAL_REQUIRED_FIELDS = (
    "id",
    "proposed_by",
    "proposed_at",
    "cost",
    "limitation_solved",
    "expected_benefit",
    "free_alternatives_considered",
    "evidence",
)
DECISION_REQUIRED_FIELDS = ("proposal_id", "decision", "decided_by", "decided_at", "rationale")
VALID_DECISIONS = {"APPROVED", "REJECTED", "DEFERRED"}


def load_proposals(path: Path = PROPOSED_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        raise RuntimeError("resource_recommendations_proposed.json must contain a list of proposals")
    seen: set[str] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise RuntimeError("proposal entry must be an object")
        missing = [field for field in PROPOSAL_REQUIRED_FIELDS if field not in proposal]
        if missing:
            raise RuntimeError(f"proposal missing required fields: {missing}")
        proposal_id = str(proposal["id"])
        if proposal_id in seen:
            raise RuntimeError(f"duplicate proposal id: {proposal_id}")
        seen.add(proposal_id)
    return proposals


def load_decisions(path: Path = DECISIONS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise RuntimeError("resource_recommendations_decisions.json must contain a list of decisions")
    for decision in decisions:
        if not isinstance(decision, dict):
            raise RuntimeError("decision entry must be an object")
        missing = [field for field in DECISION_REQUIRED_FIELDS if field not in decision]
        if missing:
            raise RuntimeError(f"decision missing required fields: {missing}")
        if decision["decision"] not in VALID_DECISIONS:
            raise RuntimeError(f"decision must be one of {VALID_DECISIONS}: {decision['decision']}")
    return decisions


def is_approved(proposal_id: str, decisions: list[dict[str, Any]] | None = None) -> bool:
    """True only if a human/Lead decision entry approves this exact proposal id.

    A proposal existing in resource_recommendations_proposed.json never
    implies approval by itself -- this function is the only place that
    grants that meaning, and it can only return True from a decision entry,
    which no autonomous engine role can write.
    """
    active = decisions if decisions is not None else load_decisions()
    return any(d["proposal_id"] == proposal_id and d["decision"] == "APPROVED" for d in active)


def unresolved_proposal_ids(
    proposals: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> list[str]:
    active_proposals = proposals if proposals is not None else load_proposals()
    active_decisions = decisions if decisions is not None else load_decisions()
    decided_ids = {d["proposal_id"] for d in active_decisions}
    return [str(p["id"]) for p in active_proposals if str(p["id"]) not in decided_ids]

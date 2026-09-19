"""One bounded observe -> persist -> update -> route research cycle."""

from __future__ import annotations

from .research_bridge import emit_research_hypotheses, rank_research_missions


def process_observation(memory, contract, evidence, *, as_of):
    """Persist one immutable observation and derive the same-mechanism state.

    Storage failures and malformed evidence intentionally propagate: callers must
    WAIT rather than continue from an empty or partially remembered state.
    """
    memory.freeze(contract)
    memory.append_evidence(evidence)
    snapshot = memory.snapshot(as_of=as_of)
    mechanism = snapshot["mechanisms"].get(contract["mechanism_id"])
    if mechanism is None:
        raise ValueError("persisted mechanism missing from snapshot")
    hypotheses = emit_research_hypotheses(snapshot)
    missions = rank_research_missions(snapshot)
    return {
        "schema_version": 1,
        "mechanism_id": contract["mechanism_id"],
        "state": mechanism["state"],
        "research_hypotheses": hypotheses,
        "ranked_missions": missions,
        "research_only": True,
        "automatic_execution_authority": False,
        "strategy_mutation_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
    }

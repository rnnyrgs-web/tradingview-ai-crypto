"""Safe bridge from token-free logical specialists into the quant-science queue.

Specialist findings are advisory hypotheses. Only findings that already map to a
canonical single-dimension experiment understood by the current evaluator are
allowed into the automatic research queue. Scoped/conjunctive findings remain
visible but deferred until a dedicated evaluator exists; scope is never silently
lost just to make a hypothesis dispatchable.
"""

from __future__ import annotations

from copy import deepcopy

from continuous_specialist_factory import build_specialist_snapshot
from research_quant_science_factory import METHOD_BY_DIMENSION

# These workers either represent the whole resolved ledger or exactly one
# canonical dimension/group supported by the restrictive evaluator. Asset- and
# conjunction-specific workers are intentionally excluded from automatic
# dispatch because the current experiment schema cannot faithfully preserve
# their extra scope.
CANONICAL_SPECIALIST_NAMES = {
    "24h-diagnostics",
    "7d-diagnostics",
    "buy-errors",
    "sell-errors",
    "bull-regime",
    "bear-regime",
    "sideways-regime",
    "unknown-regime",
    "score-90-plus",
    "score-80-89",
    "score-70-79",
    "score-60-69",
    "score-below-60",
    "horizon-priority",
    "direction-priority",
    "regime-priority",
    "score-priority",
    "strategy-priority",
}


def _identity(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("dimension") or "unknown"),
        str(item.get("group") or "unknown"),
        str(item.get("target_horizon") or "both"),
    )


def enrich_diagnostics_with_specialists(rows: list[dict], diagnostics: dict) -> tuple[dict, dict]:
    """Merge safe specialist hypotheses into diagnostics without weakening scope.

    Returns enriched diagnostics plus a bounded audit report describing which
    logical-specialist findings were accepted or deferred.
    """
    enriched = deepcopy(diagnostics)
    workers = build_specialist_snapshot(rows)
    base_priorities = [dict(item) for item in (enriched.get("research_priorities") or []) if isinstance(item, dict)]
    by_identity = {_identity(item): item for item in base_priorities}
    accepted: list[dict] = []
    deferred: list[dict] = []

    for name, worker in sorted(workers.items()):
        candidate = worker.get("top_falsifiable_hypothesis") if isinstance(worker, dict) else None
        if not isinstance(candidate, dict):
            continue
        dimension = str(candidate.get("dimension") or "")
        reason = None
        if name not in CANONICAL_SPECIALIST_NAMES:
            reason = "specialist_scope_requires_dedicated_evaluator"
        elif dimension not in METHOD_BY_DIMENSION:
            reason = "unsupported_experiment_dimension"
        elif candidate.get("requires_new_validation") is not True:
            reason = "not_a_fresh_validation_hypothesis"

        if reason:
            deferred.append({
                "specialist": name,
                "dimension": dimension or None,
                "group": candidate.get("group"),
                "reason": reason,
            })
            continue

        identity = _identity(candidate)
        existing = by_identity.get(identity)
        if existing is None:
            merged = dict(candidate)
            merged["specialist_sources"] = [name]
            by_identity[identity] = merged
            base_priorities.append(merged)
        else:
            sources = list(existing.get("specialist_sources") or [])
            if name not in sources:
                sources.append(name)
            existing["specialist_sources"] = sorted(sources)
            if float(candidate.get("priority_score") or 0.0) > float(existing.get("priority_score") or 0.0):
                for key in (
                    "samples", "independent_samples", "wrong_rate", "priority_score",
                    "research_question", "hypothesis", "predicted_mechanism",
                    "expected_signal_quality_effect", "evidence_needed", "falsification_criteria",
                    "chronological_oos_requirements", "realistic_cost_treatment",
                    "independent_sample_requirements", "requires_new_validation",
                ):
                    if key in candidate:
                        existing[key] = candidate[key]
        accepted.append({
            "specialist": name,
            "dimension": identity[0],
            "group": identity[1],
            "target_horizon": identity[2],
        })

    base_priorities.sort(
        key=lambda item: (
            -float(item.get("priority_score") or 0.0),
            -int(item.get("independent_samples") or 0),
            str(item.get("dimension") or ""),
            str(item.get("group") or ""),
        )
    )
    enriched["research_priorities"] = base_priorities[:20]
    audit = {
        "ok": True,
        "research_only": True,
        "logical_specialists_seen": len(workers),
        "accepted_candidate_count": len(accepted),
        "deferred_candidate_count": len(deferred),
        "accepted_candidates": accepted[:20],
        "deferred_candidates": deferred[:20],
        "scope_loss_allowed": False,
        "automatic_strategy_mutation": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    return enriched, audit

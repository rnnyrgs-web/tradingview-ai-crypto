"""Caller-side integration; existing validation and worker eligibility stay intact."""
from copy import deepcopy
from dataclasses import replace
import os
import sqlite3
from threading import Lock

from money_intelligence_mission_integration import apply_causal_feedback

from .analytics import analyze
from .contracts import SAFE, fingerprint, strategy_semantic_fingerprint
from .evolution import learning_missions, rank_candidates
from .memory import Memory

_lock = Lock()
_director_state = None


def _configured_memory():
    path = os.getenv("PROFITABILITY_LEARNING_DB", "").strip()
    if path:
        return Memory(path, create=False)
    # Production already has an approved service-role Supabase channel. Prefer
    # it to an ephemeral local file and fail closed if its schema is unavailable.
    import db
    if db.configured():
        from .supabase_memory import SupabaseMemory
        return SupabaseMemory()
    return None


def complete_experiment(experiment, *, ablation=None):
    """Shared rich completion entry point for Python workers and CLI ingestion."""
    memory = _configured_memory()
    if memory is None:
        result = analyze(experiment)
        return {**result, "persistence_status": "WAIT_MEMORY_NOT_CONFIGURED",
                "research_complete": False, "required_action": "Configure initialized durable research memory"}
    result = memory.complete(experiment, ablation=ablation)
    return {**result, "persistence_status": "PERSISTED", "research_complete": True}


def learning_snapshot():
    memory = _configured_memory()
    if memory is None:
        return {"status": "WAIT_MEMORY_NOT_CONFIGURED", "memory": None, **SAFE}
    return {"status": "AVAILABLE", "memory": memory.snapshot(), **SAFE}


def enrich_legacy_lesson(lesson):
    """Preserve missing-evidence learning inside the existing durable lesson JSON."""
    result = deepcopy(lesson)
    summary = result.get("evidence_summary")
    if not isinstance(summary, dict):
        summary = {} if summary is None else {"legacy_summary": summary}
    outcome = result.get("outcome")
    classification = "INFRA_DATA_FAILURE" if outcome in {"infra_data_failure", "insufficient_history"} else "INCONCLUSIVE"
    summary["profitability_learning"] = {
        "schema_version": 1, "outcome": classification,
        "economic_metrics_available": False, "component_effects_available": False,
        "limitation": "Legacy summary lacks frozen contract, reconciled NAV and component ablation evidence.",
        "next_action": "Emit a versioned economic experiment completion artifact before economic/component conclusions.",
        **SAFE}
    result["evidence_summary"] = summary
    memory = _configured_memory()
    if memory is not None:
        # Ignore volatile recorded_at and nested derived fields for replay identity.
        source = {k: lesson.get(k) for k in ("fingerprint", "hypothesis", "outcome", "evidence_summary", "recommended_next_test", "reason_not_to_repeat")}
        memory.record_legacy(source)
    return result


def factory_feedback():
    try:
        state = learning_snapshot()
    except (ValueError, OSError, sqlite3.Error):
        return {"status": "WAIT_MEMORY_UNAVAILABLE", "missions": [], "allocation": {},
                "progress_metric": "credible_economic_evidence_or_uncertainty_reduction", **SAFE}
    memory = state["memory"]
    missions = learning_missions(memory) if memory is not None else []
    weights = {mode: sum(m["learning_priority"] for m in missions if m["mode"] == mode)
               for mode in ("EXPLORE", "EXPLOIT", "LEARN")}
    total = sum(weights.values())
    return {"status": state["status"], "missions": missions,
            "allocation": {k: v / total if total else 0.0 for k, v in weights.items()},
            "allocation_semantics": "Advisory weights from current evidence, not worker quotas or trading authority",
            "progress_metric": "credible_economic_evidence_or_uncertainty_reduction", **SAFE}


def _candidate_feedback(candidate, memory):
    ident = candidate.get("experiment_id")
    prior = [r for r in memory.get("legacy_outcomes", []) if ident and r.get("experiment_id") == ident]
    factor, reason = 1.0, "no_matched_completion"
    if prior:
        # This is a repeat-information penalty, NOT a conclusion of negative
        # economic expectancy from a sparse accuracy/validation summary.
        factor, reason = .5, "prior_completion_requires_new_evidence"
    family = candidate.get("family") or candidate.get("strategy_family")
    sf = candidate.get("strategy_fingerprint")
    semantic = None
    semantic_unverifiable = False
    if sf:
        strategy = candidate.get("strategy")
        if strategy is not None:
            try:
                if sf != fingerprint(strategy):
                    raise ValueError("strategy fingerprint mismatch")
                semantic = strategy_semantic_fingerprint(strategy)
            except (KeyError, TypeError, ValueError):
                semantic_unverifiable = True
        else:
            semantic = memory.get("strategy_semantic_by_fingerprint", {}).get(sf)
            semantic_unverifiable = semantic is None and sf not in memory.get(
                "rejected_fingerprints", []
            )
    semantic_evidence = memory.get("semantic_strategies", {}).get(semantic)
    if semantic_evidence is not None or family in memory.get("families", {}):
        ranked = rank_candidates([{
            **candidate,
            "family": family,
            "strategy_semantic_fingerprint": semantic,
            "id": ident,
        }], memory)[0]
        factor *= ranked["learning_factor"]
        reason = (
            "matched_semantic_economic_evidence"
            if semantic_evidence is not None
            else "matched_family_economic_evidence"
        )
    if sf and sf in memory.get("rejected_fingerprints", []):
        factor, reason = 0.0, "rejected_exact_fingerprint"
    elif semantic in memory.get("rejected_semantic_fingerprints", []):
        factor, reason = 0.0, "rejected_semantic_identity"
    elif semantic_unverifiable:
        factor, reason = 0.0, "semantic_identity_unverifiable"
    return {"factor": factor, "reason": reason,
            "changes_eligibility": reason in {
                "rejected_exact_fingerprint",
                "rejected_semantic_identity",
                "semantic_identity_unverifiable",
            }, **SAFE}


def apply_queue_feedback(queue):
    result = deepcopy(queue)
    try:
        state = learning_snapshot()
    except (ValueError, OSError, sqlite3.Error):
        result["learning_status"] = "WAIT_MEMORY_UNAVAILABLE"
        result["experiments"] = []
        result["experiment_count"] = 0
        return result
    result["learning_status"] = state["status"]
    if state["memory"] is None:
        return result
    for row in result.get("experiments", []):
        feedback = _candidate_feedback(row, state["memory"])
        row["learning_feedback"] = feedback
        # Re-entry must not compound the same evidence penalty a second time.
        base = float(row.get("base_information_priority", row.get("information_priority", 0)))
        row["base_information_priority"] = base
        row["information_priority"] = base * feedback["factor"]
    result["experiments"].sort(key=lambda r: (-r["information_priority"], str(r.get("experiment_id", ""))))
    return result


def refresh_director(army):
    """Decorate the existing director through its caller; do not edit PR #387 files."""
    from research_director_runtime import refresh_director as legacy_refresh
    from research_director import build_mission
    global _director_state
    result = deepcopy(legacy_refresh(army))
    feedback = factory_feedback()
    result["profitability_learning"] = feedback
    if feedback["status"] == "WAIT_MEMORY_UNAVAILABLE":
        result["next_missions"] = []
    # Missing/corrupt configured memory does not authorize stale learned missions.
    if feedback["status"] == "AVAILABLE":
        memory = learning_snapshot()["memory"]
        worker_identities = {}
        for worker in (army.get("workers") or {}).values():
            evidence = worker.get("latest_evidence", {}) if isinstance(worker, dict) else {}
            experiment = evidence.get("experiment", {}) if isinstance(evidence, dict) else {}
            if isinstance(experiment, dict) and experiment.get("experiment_id"):
                worker_identities[experiment["experiment_id"]] = experiment
        for row in result["missions"]:
            identity = worker_identities.get(row.get("experiment_id"), {})
            matched = _candidate_feedback({**identity, "experiment_id": row.get("experiment_id")}, memory)
            row["priority"] *= matched["factor"]
            row["learning_feedback"] = matched
        by_id = {m["mission_id"]: m for m in result["missions"]}
        # Never broaden legacy eligibility or disturb active claims. A remembered
        # exact rejection is a veto, not a low-priority runnable experiment.
        result["next_missions"] = sorted([deepcopy(by_id[m["mission_id"]]) for m in result["next_missions"]
            if not by_id[m["mission_id"]]["learning_feedback"]["changes_eligibility"]],
                                        key=lambda m: (-m["priority"], m["mission_id"]))
        for item in feedback["missions"]:
            mission = build_mission(lane="profitability-learning", horizon="fresh_chronological",
                direction="RESEARCH_ONLY", theme=item["id"], hypothesis=item["hypothesis"],
                expected_information_gain=item["information_gain"], expected_signal_impact=0,
                expected_profitability_impact=item["expected_economic_upside"],
                sample_readiness=item["data_readiness"], novelty=.5,
                compute_cost=item["compute_cost"], experiment_id=item["source_experiment_id"],
                blocker=item["status"])
            mission = replace(mission, priority=item["learning_priority"])
            row = {**mission.to_dict(), "learning_mode": item["mode"], **SAFE}
            result["missions"].append(row)
        result["missions"].sort(key=lambda m: (-m["priority"], m["mission_id"]))
    # These missions request contract/review work. They never enter next_missions,
    # claim an existing heavy slot or alter canonical strategy selection.
    if feedback["status"] in {"AVAILABLE", "WAIT_MEMORY_UNAVAILABLE"}:
        # The reporting surface must not revive rejected/stale recommendations.
        result["daily_lead_report"]["highest_priority_next_missions"] = deepcopy(result["next_missions"])
    result["daily_lead_report"]["profitability_learning"] = feedback
    # Phase-2 causal memory is consumed here, on the same default director surface
    # used by continuous_coordinator. The adapter itself is evidence-gated and
    # fail-closed, so unavailable/corrupt memory cannot authorize stale missions.
    result = apply_causal_feedback(result)
    with _lock:
        _director_state = deepcopy(result)
    return result


def director_snapshot():
    from research_director_runtime import snapshot
    with _lock:
        return deepcopy(_director_state) if _director_state is not None else snapshot()

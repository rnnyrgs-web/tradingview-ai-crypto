"""Evidence-aware proposals and advisory priorities. No auto-promotion or trading."""
from copy import deepcopy
from datetime import timedelta

from .contracts import (DEVELOPMENT, SAFE, VERIFIED_FAVORABLE_EVIDENCE,
                        fingerprint, number, text, timestamp, validate_contract,
                        strategy_semantic_fingerprint)


def _shape(strategy):
    # Exclude labels, parameters, assets, timeframe and economic prose so trivial
    # sweeps cannot become materially distinct merely by changing their hash.
    return sorted((c["kind"], c["rule"]) for c in strategy["components"])


def generate_hypotheses(record):
    """Automatically preserve specific, falsifiable development successors.

    These are rule-complete drafts, not executable experiments. A new contract,
    independent economic/novelty review and fresh chronology must be supplied.
    """
    c = record["contract"]
    if c["split"] not in DEVELOPMENT or record["outcome"] in {"INFRA_DATA_FAILURE", "INCONCLUSIVE"}:
        return []
    drafts = []
    for effect in record["component_evidence"]:
        if effect["independent_event_count"] < c["minimum_events"] or effect["delta_compounded_return"] >= 0:
            continue
        strategy = deepcopy(c["strategy"])
        strategy["components"] = [x for x in strategy["components"] if fingerprint(x) != effect["component_fingerprint"]]
        if not strategy["components"]:
            continue
        drafts.append(("COMPONENT_REPLACEMENT", strategy,
            f"Removing {effect['component']['kind']} ({effect['component']['rule']}) improved development NAV; test whether retained mechanism survives with the remaining exit/risk rules. Independent executable-rule review required.",
            "Reject if improvement disappears after costs on fresh chronological replication."))
    for candidate in record["conditional_hypotheses"]:
        strategy = deepcopy(c["strategy"])
        strategy["components"].append({"kind": "regime_filter", "rule": "pretrade_categorical_condition",
            "parameters": candidate["condition"],
            "economic_reason": "A development association suggests the mechanism depends on pre-trade state; causal interpretation remains unproved."})
        drafts.append(("CONDITIONAL_EDGE", strategy,
            "Pre-trade conditioning improved economic contribution after full-search correction; test the frozen condition against an unconditional matched baseline.",
            "Reject if conditional improvement fails on fresh chronological matched controls."))
    out = []
    for kind, strategy, reason, falsifier in drafts[:8]:
        sf = fingerprint(strategy)
        out.append({"hypothesis_id": fingerprint({"parent": record["experiment_id"], "strategy": sf}),
            "semantic_id": fingerprint({"parent_strategy": c["strategy_fingerprint"], "rules": _shape(strategy)}),
            "strategy": strategy, "strategy_fingerprint": sf, "kind": kind,
            "economic_reason": reason, "falsifier": falsifier,
            "ancestry": {"experiment_id": record["experiment_id"], "strategy_fingerprint": c["strategy_fingerprint"],
                "component_fingerprints": [fingerprint(x) for x in strategy["components"] if x in c["strategy"]["components"]]},
            "status": "BLOCKED_FRESH_CONTRACT_REQUIRED", "requires_independent_economic_review": True, **SAFE})
    return out


def propose_successor(memory, parent_id, contract, *, economic_reason, falsifier, external_ancestry=None):
    parent = next((r for r in memory["experiments"] if r["experiment_id"] == parent_id), None)
    if not parent or parent["contract"]["split"] not in DEVELOPMENT:
        raise ValueError("successor inspiration requires development evidence")
    c = deepcopy(validate_contract(contract))
    pc = parent["contract"]
    if c["split"] not in DEVELOPMENT:
        raise ValueError("successor first test must use fresh development evidence")
    if _shape(c["strategy"]) == _shape(pc["strategy"]):
        raise ValueError("successor needs a materially distinct rule, not parameters or labels")
    if c["strategy_fingerprint"] in memory["rejected_fingerprints"] or c["strategy_fingerprint"] == pc["strategy_fingerprint"]:
        raise ValueError("rejected or unchanged fingerprint")
    inspiration_end = max(timestamp(pc["end"]), timestamp(pc["outcomes_observed_at"]))
    # All observed windows are unavailable as fresh confirmation, not just parent.
    for r in memory["experiments"]:
        rc = r["contract"]
        if not (timestamp(c["end"]) < timestamp(rc["start"]) or timestamp(c["start"]) > timestamp(rc["end"])):
            raise ValueError("successor reuses previously observed chronology")
    guard = max(pc["embargo_seconds"], pc["purge_seconds"], c["embargo_seconds"], c["purge_seconds"])
    if timestamp(c["frozen_at"]) < inspiration_end or timestamp(c["start"]) <= inspiration_end + timedelta(seconds=guard):
        raise ValueError("fresh post-inspiration chronological data and embargo required")
    if c["dataset_sha256"] in {r["contract"]["dataset_sha256"] for r in memory["experiments"]}:
        raise ValueError("fresh dataset fingerprint required")
    text(economic_reason, "economic reason")
    text(falsifier, "falsifier")
    external = deepcopy(external_ancestry or [])
    if len(external) > 16:
        raise ValueError("ancestry bound exceeded")
    for item in external:
        if not isinstance(item, dict) or item.get("kind") not in {"MONEY_INTELLIGENCE", "BIG_MOVE", "MISSED_MOVE", "CAUSAL_REPRICING"}:
            raise ValueError("invalid external ancestry")
        text(item.get("evidence_ref"), "ancestry evidence reference")
        if timestamp(item.get("available_at")) > timestamp(c["frozen_at"]):
            raise ValueError("future external ancestry")
    ancestry = {"experiment_ids": [parent_id], "strategy_fingerprints": [pc["strategy_fingerprint"]],
        "component_fingerprints": sorted(fingerprint(comp) for comp in pc["strategy"]["components"]
            if comp in c["strategy"]["components"]), "failure_lesson": parent["outcome"],
        "economic_mechanism": pc["strategy"]["mechanism"], "external_findings": external}
    semantic = fingerprint({"rules": _shape(c["strategy"]), "parent": pc["strategy_fingerprint"]})
    return {"schema_version": 1, "proposal_id": fingerprint({"semantic": semantic, "contract": c}),
        "semantic_id": semantic, "contract": c, "strategy_fingerprint": c["strategy_fingerprint"],
        "economic_reason": economic_reason, "falsifier": falsifier, "ancestry": ancestry,
        "status": "FROZEN_RESEARCH_HYPOTHESIS_REQUIRES_REVIEW",
        "requires_fresh_chronological_validation": True,
        "novelty_review": "Rule-name comparison cannot prove economic novelty; independent review required.", **SAFE}


def validate_proposal(proposal, memory):
    ancestry = proposal.get("ancestry", {})
    parent = ancestry.get("experiment_ids", [])
    if len(parent) != 1:
        raise ValueError("one auditable parent experiment required")
    expected = propose_successor(memory, parent[0], proposal["contract"],
        economic_reason=proposal["economic_reason"], falsifier=proposal["falsifier"],
        external_ancestry=ancestry.get("external_findings"))
    if proposal != expected:
        raise ValueError("proposal identity or authority mismatch")
    for prior in memory["proposals"]:
        if prior["semantic_id"] == proposal["semantic_id"] and prior["proposal_id"] != proposal["proposal_id"]:
            raise ValueError("duplicate economic hypothesis; parameter sweep suppressed")


def rank_candidates(candidates, memory):
    """Bounded advisory evidence feedback; hard eligibility remains outside scores."""
    rows = []
    for c in candidates:
        row = deepcopy(c)
        family = memory.get("families", {}).get(c.get("family"), {})
        semantic = memory.get("semantic_strategies", {}).get(
            c.get("strategy_semantic_fingerprint"), {}
        )
        evidence = semantic or family
        failures = evidence.get("development_failures", 0)
        promising = evidence.get("promising_development", 0)
        factor = max(.1, 1 / (1 + .3 * failures))
        if evidence.get("mechanism_dead"):
            factor *= .25
        factor *= 1 + min(.3, promising * .1)
        component_votes = []
        for key in set(c.get("component_fingerprints", [])):
            evidence = memory.get("components", {}).get(key, {})
            observations = [o for o in evidence.get("observations", [])
                       if o["split"] in DEVELOPMENT and o.get("effect")
                       and o["effect"]["independent_event_count"] >= o["minimum_events"]
                       and (o.get("favorable_evidence_verified")
                            or o["effect"]["delta_compounded_return"] <= 0)]
            independent = []
            # Select within DEVELOPMENT first. Relabelled/overlapping windows
            # cannot add a vote or displace evidence with an OOS observation.
            for observation in sorted(observations, key=lambda o: timestamp(o["end"])):
                if all(timestamp(observation["start"]) > timestamp(old["end"])
                       or timestamp(observation["end"]) < timestamp(old["start"]) for old in independent):
                    independent.append(observation)
            effects = [o["effect"] for o in independent]
            if effects:
                # Median sign contribution, capped once per component. Repeated
                # occurrences never count as independent proof or extra votes.
                signs = sorted(1 if e["delta_compounded_return"] > 0 else -1 if e["delta_compounded_return"] < 0 else 0 for e in effects)
                component_votes.append(signs[len(signs) // 2])
        component_factor = 1 + (.15 * sum(component_votes) / len(component_votes) if component_votes else 0)
        factor *= component_factor
        mode = "EXPLOIT" if promising and not evidence.get("mechanism_dead") else "EXPLORE"
        if evidence.get("infra_blocked"):
            mode, factor = "LEARN", factor * .2
        def unit(key, default):
            value = number(c.get(key, default), key, minimum=0)
            if value > 1:
                raise ValueError(f"{key} must be normalized to [0,1]")
            return value
        value = (.4 * unit("expected_economic_upside", .5) + .3 * unit("information_gain", .5)
                 + .15 * unit("mechanism_strength", .5) + .15 * unit("prior_robustness", .5))
        value *= .5 + .5 * unit("uncertainty_resolution_probability", .5)
        value *= .75 + .25 * unit("novelty", .5)
        cost = 1 + unit("compute_cost", .5) + unit("monetary_cost", 0) + unit("time_to_result", .5)
        score = number(c.get("base_priority", 1), "base_priority", minimum=0) * value * unit("data_readiness", 1) * factor / cost
        blocked = (c.get("blocker")
            or c.get("strategy_fingerprint") in memory.get("rejected_fingerprints", [])
            or c.get("strategy_semantic_fingerprint") in memory.get("rejected_semantic_fingerprints", []))
        row.update({"learning_priority": 0.0 if blocked else round(score, 8), "mode": mode,
                    "learning_factor": factor, "component_factor": component_factor,
                    "learning_evidence": evidence, **SAFE})
        rows.append(row)
    return sorted(rows, key=lambda r: (-r["learning_priority"], str(r.get("id", ""))))


def learning_missions(memory, *, limit=20):
    missions = []
    for r in memory.get("experiments", []):
        if r["contract"]["split"] not in DEVELOPMENT:
            continue
        outcome = r["outcome"]
        favorable_verified = (
            r.get("favorable_evidence_provenance")
            == VERIFIED_FAVORABLE_EVIDENCE
        )
        semantic = strategy_semantic_fingerprint(r["contract"]["strategy"])
        rejected = (r["contract"]["strategy_fingerprint"] in memory.get("rejected_fingerprints", [])
            or semantic in memory.get("rejected_semantic_fingerprints", []))
        mode = "EXPLOIT" if outcome == "SUCCESS_LEARN" else "EXPLORE" if outcome == "MECHANISM_DEAD" else "LEARN"
        if mode == "EXPLOIT" and not favorable_verified:
            mode = "LEARN"
        if rejected and mode == "EXPLOIT":
            mode = "LEARN"
        hypothesis = r["next_research_question"]
        if rejected and outcome == "SUCCESS_LEARN":
            hypothesis = "Investigate contradictory evidence/provenance; the original fingerprint remains rejected and may not be retested."
        elif outcome == "SUCCESS_LEARN" and not favorable_verified:
            hypothesis = "Bind the result to a verifier-issued executor receipt before using favorable economics."
        missions.append({"id": "learning-" + r["experiment_id"], "family": r["contract"]["family"],
            "strategy_fingerprint": r["contract"]["strategy_fingerprint"] if mode == "EXPLOIT" else None,
            "hypothesis": hypothesis,
            "source_experiment_id": r["experiment_id"],
            "mode": mode, "base_priority": 1, "information_gain": .8,
            "expected_economic_upside": .6 if mode == "EXPLOIT" else .4,
            "data_readiness": .2 if outcome == "INFRA_DATA_FAILURE" else .8,
            "compute_cost": .2, "status": "RESEARCH_DESIGN_REQUIRED", **SAFE})
        for h in r.get("successor_hypotheses", []):
            missions.append({"id": h["semantic_id"], "family": r["contract"]["family"],
                "hypothesis": h["economic_reason"], "source_experiment_id": r["experiment_id"],
                "mode": "EXPLORE", "base_priority": 1.1, "information_gain": .85,
                "expected_economic_upside": .5, "data_readiness": .5, "compute_cost": .3,
                "status": h["status"], **SAFE})
    for p in memory.get("proposals", []):
        missions.append({"id": p["proposal_id"], "family": p["contract"]["family"],
            "hypothesis": p["economic_reason"], "source_experiment_id": p["ancestry"]["experiment_ids"][0],
            "mode": "EXPLORE", "base_priority": 1, "information_gain": .8,
            "expected_economic_upside": .5, "data_readiness": .5,
                "compute_cost": .5, "status": p["status"], **SAFE})
    for r in memory.get("legacy_outcomes", []):
        missions.append({"id": "legacy-learning-" + r["source_fingerprint"], "family": "missing_economic_evidence",
            "hypothesis": "Add the missing frozen economic contract, reconciled NAV and component evidence to this completed experiment.",
            "source_experiment_id": r.get("experiment_id") or r["source_fingerprint"],
            "mode": "LEARN", "base_priority": 1, "information_gain": .9,
            "expected_economic_upside": .4, "data_readiness": .5, "compute_cost": .2,
            "status": "RESEARCH_DESIGN_REQUIRED", **SAFE})
    if not missions:
        return []
    missions = list({row["id"]: row for row in missions}.values())
    modes = {r["id"]: r["mode"] for r in missions}
    ranked = rank_candidates(missions, memory)
    for row in ranked:
        row["mode"] = modes[row["id"]]
    return ranked[:max(0, min(limit, 20))]

"""Bounded predeclared development diagnostics; protected partitions are refused."""
from copy import deepcopy
from itertools import combinations
import random

from .analytics import analyze
from .contracts import (DEVELOPMENT, SAFE, fingerprint, independent_blocks, net_pnl,
                        timestamp, validate_contract, validate_experiment)


def _development(c):
    if c.get("split") not in DEVELOPMENT:
        raise ValueError("development evidence only")


def run_ablation(contract, dataset, evaluator):
    """Evaluate full, each predeclared omission and predeclared factorial pairs.

    Evaluator is a local callable(strategy, isolated_dataset) returning a trade
    ledger and NAV series. It must implement the rule omissions faithfully; this
    interface does not infer an executable strategy from prose.
    """
    _development(contract)
    c = deepcopy(validate_contract(contract))
    if not isinstance(dataset, dict) or any(dataset.get(k) != c[k] for k in ("split", "start", "end")):
        raise ValueError("dataset partition mismatch")
    if fingerprint(dataset) != c["dataset_sha256"]:
        raise ValueError("dataset fingerprint mismatch")
    if not isinstance(dataset.get("rows"), list) or not 1 <= len(dataset["rows"]) <= 100_000:
        raise ValueError("bounded timestamped dataset rows required")
    previous = None
    for row in dataset["rows"]:
        at = timestamp(row.get("timestamp"))
        available = timestamp(row.get("available_at"))
        if (not timestamp(c["start"]) <= at < timestamp(c["end"])
                or available > at or (previous is not None and at <= previous)):
            raise ValueError("dataset row chronology outside development window")
        previous = at
    omitted = [()] + [(x,) for x in c["ablation_components"]]
    omitted += sorted({tuple(sorted(pair)) for pair in c["interaction_pairs"]})
    if len(omitted) > c["search_budget"]:
        raise ValueError("ablation search budget exceeded")
    variants = []
    for remove in omitted:
        strategy = deepcopy(c["strategy"])
        strategy["components"] = [x for x in strategy["components"] if fingerprint(x) not in remove]
        if not strategy["components"]:
            raise ValueError("ablation cannot remove all executable components")
        isolated = deepcopy(dataset)
        supplied_strategy = deepcopy(strategy)
        result = evaluator(supplied_strategy, isolated)
        if fingerprint(isolated) != c["dataset_sha256"] or supplied_strategy != strategy:
            raise ValueError("ablation evaluator mutated its inputs")
        variant = {**c, "strategy": strategy, "strategy_fingerprint": fingerprint(strategy),
                   "ablation_components": [], "interaction_pairs": []}
        if not isinstance(result, dict) or "contract" in result:
            raise ValueError("evaluator cannot replace frozen contract")
        e = {**result, "contract": variant}
        analyze(e)  # verify each complete ledger before accepting any artifact
        variants.append({"omitted": list(remove), "experiment": e})
    return {"schema_version": 1, "contract": c, "variants": variants, **SAFE}


def component_effects(ablation):
    """Recompute effects from ledgers; never trust supplied metric deltas."""
    c = validate_contract(ablation["contract"])
    _development(c)
    expected = {()} | {(x,) for x in c["ablation_components"]} | {tuple(sorted(p)) for p in c["interaction_pairs"]}
    variants = ablation.get("variants", [])
    if {tuple(sorted(x["omitted"])) for x in variants} != expected or len(variants) != len(expected):
        raise ValueError("ablation variants do not match frozen plan")
    reports = {}
    for v in variants:
        key = tuple(sorted(v["omitted"]))
        ec = v["experiment"]["contract"]
        strategy = deepcopy(c["strategy"])
        strategy["components"] = [x for x in strategy["components"] if fingerprint(x) not in key]
        expected_contract = {**c, "strategy": strategy, "strategy_fingerprint": fingerprint(strategy),
                             "ablation_components": [], "interaction_pairs": []}
        if ec != expected_contract:
            raise ValueError("ablation chronology, costs or rules differ")
        reports[key] = analyze(v["experiment"])
        if not reports[key]["metrics"]:
            raise ValueError("ablation has missing economic evidence")
    full = reports[()]
    components = []
    for comp in c["strategy"]["components"]:
        ident = fingerprint(comp)
        if (ident,) not in reports:
            continue
        other = reports[(ident,)]["metrics"]
        metrics = full["metrics"]
        components.append({
            "component_fingerprint": ident, "component": comp,
            "delta_compounded_return": metrics["compounded_net_return"] - other["compounded_net_return"],
            "delta_max_drawdown": metrics["max_drawdown"] - other["max_drawdown"],
            "delta_tail_loss_money": (metrics["worst_trade_money"] or 0) - (other["worst_trade_money"] or 0),
            "delta_costs_money": sum(metrics["costs"].values()) - sum(other["costs"].values()),
            "delta_capital_utilization": metrics["average_gross_exposure_over_initial_capital"] - other["average_gross_exposure_over_initial_capital"],
            "sample_count": metrics["sample_count"],
            "independent_event_count": min(metrics["independent_event_count"], other["independent_event_count"]),
            "evidence_level": "DEVELOPMENT_ASSOCIATION", "proven": False,
            "uncertainty": "Descriptive ablation; interactions and selection may explain the difference.",
        })
    interactions = []
    for a, b in sorted({tuple(sorted(p)) for p in c["interaction_pairs"]}):
        value = lambda key: reports[key]["metrics"]["compounded_net_return"]
        interactions.append({"component_fingerprints": [a, b],
            "delta_compounded_return": value(()) - value((a,)) - value((b,)) + value((a, b)),
            "evidence_level": "DEVELOPMENT_INTERACTION_HYPOTHESIS", "proven": False,
            "uncertainty": "Factorial difference on one development window; requires fresh replication."})
    return {"components": components, "interactions": interactions, "full": full, **SAFE}


def _matches(trade, condition):
    return all(trade["features"].get(k, {}).get("value") == v for k, v in condition.items())


def mine_conditions(experiment):
    _development(experiment["contract"])
    e = validate_experiment(experiment)
    c = e["contract"]
    if e["status"] == "INFRA_DATA_FAILURE":
        return {"conditions": [], "searches": 0, **SAFE}
    dimensions = c["mining_dimensions"]
    conditions = set()
    for t in e["trades"]:
        available = [(d, t["features"][d]["value"]) for d in dimensions if d in t["features"]]
        conditions.update((pair,) for pair in available)
        conditions.update(tuple(pair) for pair in combinations(available, 2))
    ablations = 1 + len(c["ablation_components"]) + len({tuple(sorted(p)) for p in c["interaction_pairs"]})
    if len(conditions) + ablations > c["search_budget"]:
        raise ValueError("conditional plus ablation search budget exceeded")
    blocks = independent_blocks(e["trades"])
    if len(blocks) > 5000:
        raise ValueError("conditional diagnostic block budget exceeded")
    out = []
    for pairs in sorted(conditions):
        condition = dict(pairs)
        groups = {True: [], False: []}
        for block in blocks:
            # Mixed/unknown membership is not an independent treatment/control.
            if any(not all(d in t["features"] for d in condition) for t in block):
                continue
            labels = {_matches(t, condition) for t in block}
            if len(labels) == 1:
                groups[labels.pop()].append(sum(net_pnl(t) for t in block) / c["initial_capital"])
        selected, control = groups[True], groups[False]
        if min(len(selected), len(control)) < c["minimum_events"] or sum(selected) <= 0:
            continue
        observed = sum(selected) / len(selected) - sum(control) / len(control)
        if observed <= 0:
            continue
        # Deterministic block-label randomization. Exchangeability is an assumption,
        # not proof of causal effect; fresh chronological validation is mandatory.
        # Deterministic statistical permutation, not security randomness.
        rng = random.Random(int(fingerprint([c["dataset_sha256"], condition])[:16], 16))  # nosec B311
        values = selected + control
        exceed = 1
        for _ in range(999):
            permuted = rng.sample(values, len(values))
            delta = sum(permuted[:len(selected)]) / len(selected) - sum(permuted[len(selected):]) / len(control)
            exceed += delta >= observed - 1e-15
        raw_p = exceed / 1000
        adjusted = min(1.0, raw_p * c["search_budget"])
        if adjusted <= .05:
            out.append({"condition": condition, "raw_p": raw_p, "adjusted_p": adjusted,
                        "correction": "Bonferroni over frozen total search budget",
                        "net_contribution_to_initial_capital": sum(selected),
                        "mean_increment_over_control": observed,
                        "independent_events": len(selected), "control_events": len(control),
                        "evidence_level": "DEVELOPMENT_HYPOTHESIS_ONLY",
                        "requires_fresh_chronological_validation": True,
                        "uncertainty": "Block-label exchangeability assumed; regime/time confounding remains."})
    return {"conditions": out, "searches": len(conditions), "total_search_budget": c["search_budget"], **SAFE}

"""Authoritative, fail-closed research truth for the one-verified-edge mission.

Only evidence bound to the currently active immutable strategy fingerprint may
advance the scientific funnel. Stale, conflicting, unbound or legacy promotion
signals remain visible elsewhere as diagnostics but cannot upgrade this truth.
"""

from __future__ import annotations

from typing import Any


FUNNEL_KEYS = (
    "ideas",
    "frozen_candidates",
    "validation_pass",
    "robustness_pass",
    "oos_pass",
    "forward_pass",
    "paper_champions",
)

_STAGE_RANK = {
    "RESEARCH_PASS": 1,
    "VALIDATION_PASS": 2,
    "ROBUSTNESS_PASS": 3,
    "OOS_PASS": 4,
    "FORWARD_PENDING": 5,
    "FORWARD_PASS": 6,
}


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _status_from_bool(value: Any, *, pending: str = "UNVERIFIED") -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return pending


def _experiment_activity(director: dict) -> dict:
    daily = _dict(director.get("daily_lead_report"))
    experiments = _dict(daily.get("experiments"))
    tested = experiments.get("tested", 0)
    rejected = experiments.get("rejected", 0)
    validation_passed = experiments.get("validation_passed", 0)
    blocked = experiments.get("blocked", 0)
    try:
        tested = max(0, int(tested or 0))
        rejected = max(0, int(rejected or 0))
        validation_passed = max(0, int(validation_passed or 0))
        blocked = max(0, int(blocked or 0))
    except (TypeError, ValueError):
        return {
            "status": "UNVERIFIED",
            "completed": "UNVERIFIED",
            "rejected": "UNVERIFIED",
            "promoted": "UNVERIFIED",
            "insufficient_evidence": "UNVERIFIED",
        }
    return {
        "status": "VERIFIED",
        "completed": tested,
        "rejected": rejected,
        "promoted": validation_passed,
        "insufficient_evidence": blocked,
    }


def _matching_results(army: dict, fingerprint: str) -> list[dict]:
    results = []
    workers = _dict(army.get("workers"))
    for worker in workers.values():
        evidence = _dict(_dict(worker).get("latest_evidence"))
        rows = _list(evidence.get("canonical_candidate_results"))
        if not rows and evidence.get("strategy_fingerprint") and evidence.get("decision"):
            rows = [evidence]
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("strategy_fingerprint") or "").strip() != fingerprint:
                continue
            decision = row.get("decision")
            if isinstance(decision, dict):
                results.append(row)
    return results


def _best_result(results: list[dict]) -> dict | None:
    if not results:
        return None
    rejected = [row for row in results if _dict(row.get("decision")).get("state") == "REJECTED"]
    if rejected:
        # A falsification of the exact frozen candidate is authoritative and may not
        # be hidden by another worker's weaker/stale pass-like result.
        return sorted(
            rejected,
            key=lambda row: str(row.get("symbol") or row.get("bar") or ""),
        )[0]
    return max(
        results,
        key=lambda row: _STAGE_RANK.get(str(_dict(row.get("decision")).get("state") or ""), -1),
    )


def _funnel(*, idea_count: int, has_candidate: bool, state: str | None, production_candidate: bool) -> dict:
    funnel = {key: 0 for key in FUNNEL_KEYS}
    funnel["ideas"] = max(0, int(idea_count))
    if not has_candidate:
        return funnel
    funnel["frozen_candidates"] = 1
    if state == "REJECTED" or not state:
        return funnel
    rank = _STAGE_RANK.get(state, 0)
    if rank >= _STAGE_RANK["VALIDATION_PASS"]:
        funnel["validation_pass"] = 1
    if rank >= _STAGE_RANK["ROBUSTNESS_PASS"]:
        funnel["robustness_pass"] = 1
    if rank >= _STAGE_RANK["OOS_PASS"]:
        funnel["oos_pass"] = 1
    if state == "FORWARD_PASS":
        funnel["forward_pass"] = 1
        funnel["paper_champions"] = 1 if production_candidate else 0
    return funnel


def _scientific_status(evidence: dict, key: str) -> dict:
    row = _dict(evidence.get(key))
    if not row:
        return {"status": "UNVERIFIED"}
    status = str(row.get("status") or "").strip()
    if row.get("pass") is True:
        status = "PASS"
    elif row.get("pass") is False and not status:
        status = "FAIL"
    return {"status": status or "UNVERIFIED", **row}


def _robustness_status(evidence: dict) -> tuple[dict, dict]:
    robustness = _dict(evidence.get("robustness"))
    stability = robustness.get("parameter_neighborhood_stable")
    cost_2x = robustness.get("cost_2x_positive")
    cost_3x = robustness.get("cost_3x_acceptable")
    parameter = {"status": _status_from_bool(stability)}
    if stability is not None:
        parameter["parameter_neighborhood_stable"] = stability is True

    if cost_2x is True and cost_3x is True:
        cost_status = "PASS"
    elif cost_2x is False or cost_3x is False:
        cost_status = "FAIL"
    else:
        cost_status = "UNVERIFIED"
    cost = {"status": cost_status}
    if cost_2x is not None:
        cost["cost_2x_positive"] = cost_2x is True
    if cost_3x is not None:
        cost["cost_3x_acceptable"] = cost_3x is True
    return parameter, cost


def build_research_truth(objective: dict, director: dict, army: dict) -> dict:
    """Build one authoritative scientific snapshot for Mission Control."""
    focus = _dict(_dict(objective).get("single_strategy_focus"))
    candidate = focus.get("active_candidate")
    candidate = candidate if isinstance(candidate, dict) else None
    fingerprint = str((candidate or {}).get("fingerprint_id") or "").strip()
    missions = _list(_dict(director).get("missions"))
    idea_count = len(missions)
    activity = _experiment_activity(_dict(director))

    base = {
        "funnel": _funnel(
            idea_count=idea_count,
            has_candidate=bool(fingerprint),
            state=None,
            production_candidate=False,
        ),
        "closest_candidate": None,
        "missing_evidence": [],
        "negative_knowledge": {"status": "UNVERIFIED"},
        "experiment_activity": activity,
        "independent_reproduction": {"status": "UNVERIFIED"},
        "multiple_testing": {"status": "UNVERIFIED"},
        "cost_stress": {"status": "UNVERIFIED"},
        "parameter_stability": {"status": "UNVERIFIED"},
        "forward_evidence": {"status": "UNVERIFIED"},
        "trade_authority": False,
        "promotion_authority": False,
    }

    if not fingerprint:
        base["missing_evidence"] = ["candidate_not_frozen"]
        return base

    matching = _matching_results(_dict(army), fingerprint)
    selected = _best_result(matching)
    if selected is None:
        base["closest_candidate"] = {
            "strategy_fingerprint": fingerprint,
            "state": "UNVERIFIED",
            "blockers": ["canonical_candidate_evidence_unavailable"],
            "rejection_reasons": [],
        }
        base["missing_evidence"] = ["canonical_candidate_evidence_unavailable"]
        return base

    decision = _dict(selected.get("decision"))
    evidence = _dict(selected.get("evidence"))
    state = str(decision.get("state") or "UNVERIFIED")
    blockers = [str(value) for value in _list(decision.get("blocking_gates")) if str(value)]
    rejections = [str(value) for value in _list(decision.get("rejection_reasons")) if str(value)]
    production_candidate = decision.get("production_candidate") is True

    base["closest_candidate"] = {
        "strategy_fingerprint": fingerprint,
        "state": state,
        "blockers": blockers,
        "rejection_reasons": rejections,
        "symbol": selected.get("symbol"),
        "bar": selected.get("bar"),
        "strategy_family": selected.get("strategy_family"),
        "production_candidate": production_candidate,
        "real_money_trade_authority": False,
    }
    base["missing_evidence"] = blockers if state != "REJECTED" else rejections
    base["funnel"] = _funnel(
        idea_count=idea_count,
        has_candidate=True,
        state=state,
        production_candidate=production_candidate,
    )

    multiple = _dict(evidence.get("multiple_testing"))
    if multiple:
        base["multiple_testing"] = {
            "status": _status_from_bool(multiple.get("pass")),
            **multiple,
        }
    parameter, cost = _robustness_status(evidence)
    base["parameter_stability"] = parameter
    base["cost_stress"] = cost
    base["independent_reproduction"] = _scientific_status(evidence, "independent_reproduction")
    base["forward_evidence"] = _scientific_status(evidence, "forward")

    if state == "REJECTED":
        base["negative_knowledge"] = {
            "status": "VERIFIED",
            "strategy_fingerprint": fingerprint,
            "reasons": rejections,
        }
    else:
        base["negative_knowledge"] = {"status": "VERIFIED", "reasons": []}
    return base

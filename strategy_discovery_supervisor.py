from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestration.rejected_fingerprints import load_rejected_fingerprints

ROOT = Path(__file__).resolve().parent
DEFAULT_QUEUE = ROOT / "orchestration" / "strategy_discovery_queue.json"

ACTIVE_DEEP_STAGES = {
    "DEEP_VALIDATION",
    "OOS_VALIDATION",
    "ROBUSTNESS_VALIDATION",
    "CROSS_ENGINE_VALIDATION",
    "FORWARD_SHADOW",
}
SCREENABLE_STAGES = {"CHEAP_SCREEN_READY"}
GENERATOR_STAGES = {"INDEPENDENT_GENERATOR"}

REQUIRED_FIELDS = {
    "hypothesis_id",
    "fingerprint_id",
    "family",
    "lane",
    "stage",
    "work_mode",
    "economic_mechanism",
    "hypothesis",
    "target_markets",
    "target_timeframes",
    "source_fingerprint_required",
    "blocker",
    "expected_profitability_impact",
    "expected_information_gain",
    "falsification_value",
    "sample_readiness",
    "compute_cost",
    "validation_requirements",
}


def _unit(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be numeric") from exc
    if not 0.0 <= number <= 1.0:
        raise RuntimeError(f"{field} must be between 0 and 1")
    return number


def discovery_score(row: dict[str, Any]) -> float:
    profitability = _unit(row["expected_profitability_impact"], "expected_profitability_impact")
    information = _unit(row["expected_information_gain"], "expected_information_gain")
    falsification = _unit(row["falsification_value"], "falsification_value")
    readiness = _unit(row["sample_readiness"], "sample_readiness")
    cost = _unit(row["compute_cost"], "compute_cost")
    value = (
        0.42 * profitability
        + 0.30 * information
        + 0.16 * falsification
        + 0.12 * readiness
    )
    return round(value / (0.35 + 0.65 * cost), 6)


def load_queue(path: Path = DEFAULT_QUEUE) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_queue(payload)
    return payload


def validate_queue(payload: dict[str, Any]) -> None:
    if payload.get("lifecycle_phase") != "SELECTION" and payload.get("active_deep_candidate") is None:
        raise RuntimeError("non-selection lifecycle requires an active_deep_candidate")
    limit = payload.get("max_active_deep_candidates")
    if type(limit) is not int or limit != 1:
        raise RuntimeError("strategy discovery must allow exactly one active deep candidate")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise RuntimeError("policy missing")
    for field in ("research_only", "trade_authority", "broker_connected"):
        if field not in policy:
            raise RuntimeError(f"policy missing {field}")
    if (
        policy.get("research_only") is not True
        or policy.get("trade_authority") is not False
        or policy.get("broker_connected") is not False
    ):
        raise RuntimeError("strategy discovery must remain research-only with broker disconnected")
    for field in (
        "untouched_oos_requires_frozen_selection_pass",
        "rejected_fingerprints_are_terminal_without_new_hypothesis",
        "no_paid_api_required_for_supervisor",
    ):
        if policy.get(field) is not True:
            raise RuntimeError(f"strategy discovery policy requires {field}=true")

    rows = payload.get("candidates")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("candidate queue must be non-empty")

    rejected = {str(row["fingerprint_id"]) for row in load_rejected_fingerprints()}
    ids: set[str] = set()
    fingerprints: set[str] = set()
    deep: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("candidate must be an object")
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            raise RuntimeError(f"candidate missing fields: {missing}")

        hypothesis_id = str(row["hypothesis_id"]).strip()
        fingerprint = str(row["fingerprint_id"]).strip()
        if not hypothesis_id or hypothesis_id in ids:
            raise RuntimeError(f"duplicate or missing hypothesis_id: {hypothesis_id}")
        if not fingerprint or fingerprint in fingerprints:
            raise RuntimeError(f"duplicate or missing fingerprint_id: {fingerprint}")

        ids.add(hypothesis_id)
        fingerprints.add(fingerprint)

        if fingerprint in rejected:
            raise RuntimeError(f"queue contains rejected fingerprint: {fingerprint}")
        if not isinstance(row["target_markets"], list) or not row["target_markets"]:
            raise RuntimeError(f"{hypothesis_id} requires target_markets")
        if not isinstance(row["target_timeframes"], list) or not row["target_timeframes"]:
            raise RuntimeError(f"{hypothesis_id} requires target_timeframes")
        if not isinstance(row["validation_requirements"], list) or not row["validation_requirements"]:
            raise RuntimeError(f"{hypothesis_id} requires validation_requirements")

        for field in (
            "expected_profitability_impact",
            "expected_information_gain",
            "falsification_value",
            "sample_readiness",
            "compute_cost",
        ):
            _unit(row[field], field)

        if (
            row["source_fingerprint_required"] is True
            and row["stage"] == "BLOCKED_SOURCE_FINGERPRINT"
            and not row.get("blocker")
        ):
            raise RuntimeError(f"{hypothesis_id} source-fingerprint block must be explicit")

        if row["stage"] in ACTIVE_DEEP_STAGES or row["work_mode"] == "DEEP":
            deep.append(row)

    if len(deep) > 1:
        raise RuntimeError("only one strategy may consume deep-validation capacity")

    active = payload.get("active_deep_candidate")
    if deep:
        if not isinstance(active, dict) or active.get("fingerprint_id") != deep[0]["fingerprint_id"]:
            raise RuntimeError("active_deep_candidate must match the single deep candidate")
    elif active is not None:
        raise RuntimeError("active_deep_candidate declared but no deep candidate exists")


def ranked_screens(payload: dict[str, Any]) -> list[dict[str, Any]]:
    # Public callers can supply an in-memory queue without using load_queue(),
    # or mutate it after loading. Recheck before emitting an executable task.
    validate_queue(payload)
    rows = []
    for row in payload["candidates"]:
        if row["stage"] not in SCREENABLE_STAGES or row.get("blocker"):
            continue
        item = dict(row)
        item["discovery_score"] = discovery_score(row)
        rows.append(item)

    return sorted(
        rows,
        key=lambda row: (
            row["discovery_score"],
            row["expected_profitability_impact"],
            row["expected_information_gain"],
            row["falsification_value"],
            row["hypothesis_id"],
        ),
        reverse=True,
    )


def snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    # Validate before reporting hard-coded safe authority flags or routing work.
    # A malformed queue must not masquerade as a safe research snapshot.
    validate_queue(payload)
    deep = [
        row
        for row in payload["candidates"]
        if row["stage"] in ACTIVE_DEEP_STAGES or row["work_mode"] == "DEEP"
    ]
    ranked = ranked_screens(payload)
    generators = [
        {
            "hypothesis_id": row["hypothesis_id"],
            "family": row["family"],
            "lane": row["lane"],
            "stage": row["stage"],
        }
        for row in payload["candidates"]
        if row["stage"] in GENERATOR_STAGES
    ]
    blocked = [
        {
            "hypothesis_id": row["hypothesis_id"],
            "family": row["family"],
            "stage": row["stage"],
            "blocker": row.get("blocker"),
        }
        for row in payload["candidates"]
        if row.get("blocker")
    ]

    next_action = None
    if deep:
        next_action = {
            "action": "CONTINUE_SINGLE_DEEP_VALIDATION",
            "hypothesis_id": deep[0]["hypothesis_id"],
            "fingerprint_id": deep[0]["fingerprint_id"],
        }
    elif ranked:
        next_action = {
            "action": "RUN_CHEAP_DETERMINISTIC_SCREEN",
            "hypothesis_id": ranked[0]["hypothesis_id"],
            "fingerprint_id": ranked[0]["fingerprint_id"],
            "discovery_score": ranked[0]["discovery_score"],
        }

    return {
        "schema_version": 1,
        "objective": payload["objective"],
        "lifecycle_phase": payload["lifecycle_phase"],
        "active_deep_candidate": payload["active_deep_candidate"],
        "next_action": next_action,
        "ranked_cheap_screens": [
            {
                "rank": index + 1,
                "hypothesis_id": row["hypothesis_id"],
                "fingerprint_id": row["fingerprint_id"],
                "family": row["family"],
                "discovery_score": row["discovery_score"],
            }
            for index, row in enumerate(ranked)
        ],
        "independent_generators": generators,
        "blocked_lanes": blocked,
        "research_only": True,
        "trade_authority": False,
        "broker_connected": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = load_queue(args.queue)
    result = snapshot(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.validate:
        print("strategy discovery supervisor: valid")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

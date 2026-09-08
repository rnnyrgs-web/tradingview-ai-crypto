"""Aggregate repeated sealed research runs without granting live approval."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from champion_challenger import build_champion_challenger
from research_artifact import seal_research_payload, verify_research_envelope


def aggregate_registry_artifacts(root: Path, minimum_runs: int = 3) -> dict:
    evidence = defaultdict(dict)
    invalid_artifacts = []
    valid_artifacts = 0
    for path in sorted(root.rglob("strategy_registry.json")):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid_artifacts.append(path.as_posix())
            continue
        if not verify_research_envelope(envelope):
            invalid_artifacts.append(path.as_posix())
            continue
        valid_artifacts += 1
        payload = envelope["payload"]
        evidence_hash = envelope["integrity"]["payload_sha256"]
        for item in payload.get("eligible_strategies") or []:
            if (item.get("robustness") or {}).get("passed") is not True:
                continue
            key = (item.get("symbol"), item.get("bar"), item.get("strategy_family"))
            if not all(key):
                continue
            evidence[key][evidence_hash] = {
                "generated_at": payload.get("generated_at"),
                "validation": item.get("validation"),
                "holdout_test": item.get("holdout_test"),
                "robustness": item.get("robustness"),
            }

    candidates = []
    run_history = {}
    for (symbol, bar, family), runs in sorted(evidence.items()):
        hashes = sorted(runs)
        if len(hashes) < minimum_runs:
            continue
        key = (symbol, bar, family)
        run_history[key] = [runs[digest] for digest in hashes]
        candidates.append({
            "symbol": symbol,
            "bar": bar,
            "strategy_family": family,
            "distinct_sealed_runs": len(hashes),
            "evidence_sha256": hashes,
            "status": "READY_FOR_STRATEGY_REGISTRY_REVIEW",
            "live_approved": False,
        })

    ensemble = build_champion_challenger(candidates, run_history)
    return {
        "schema_version": 2,
        "minimum_distinct_runs": minimum_runs,
        "valid_artifact_count": valid_artifacts,
        "invalid_artifacts": invalid_artifacts,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "champion_challenger": ensemble,
        "policy": (
            "Aggregation and champion/challenger weighting are research evidence only. "
            "They cannot authorize a live signal or bypass Strategy Registry / Production Risk approval."
        ),
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--minimum-runs", type=int, default=3)
    args = parser.parse_args()
    result = aggregate_registry_artifacts(Path(args.input), max(3, args.minimum_runs))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(seal_research_payload(result), indent=2) + "\n", encoding="utf-8")
    print(
        f"Aggregated {result['valid_artifact_count']} sealed artifacts; "
        f"candidates={result['candidate_count']}; ensemble={result['champion_challenger']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

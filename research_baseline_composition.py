"""Descriptive reconciliation of already-consumed candidate/baseline labels.

This is not an estimator of causal alpha, a new test, or a portfolio simulator.
Touching/overlapping holdings on ANY asset form one transitive component;
separated components can still be dependent. No significance claims are made.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from math import fsum, isfinite
from pathlib import Path

from research_artifact import verify_research_envelope


PINNED_PAYLOAD = "8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e"
PINNED_CONTRACT = "19252de4464fc997632b0500fded857bc58d5bdad49d6f72e3660eba75a28b57"
PINNED_DATASET = "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
PINNED_FINGERPRINT = "DISC-LIQUIDITY-MEANREV-001-v1"


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"invalid finite {name}")
    return float(value)


def _indexed(rows):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid trade row")
        try:
            instrument, direction = row["instrument"], row["direction"]
            if (not isinstance(instrument, str) or not instrument.strip()
                    or instrument != instrument.strip() or direction not in ("LONG", "SHORT")):
                raise ValueError("invalid instrument or direction")
            signal, entry, end = (row[k] for k in ("signal_ts", "entry_ts", "exit_ts"))
            if any(type(t) is not int or t < 0 for t in (signal, entry, end)):
                raise ValueError("timestamps must be nonnegative integers")
            if not signal < entry < end:
                raise ValueError("invalid chronology")
            key = (instrument, direction, signal, entry, end)
            if key in result:
                raise ValueError("duplicate trade identity")
            result[key] = _number(row["gross_bps"], "gross_bps")
        except KeyError as exc:
            raise ValueError("missing trade field") from exc
    return result


def _components(keys):
    groups, current, right = [], [], -1
    for key in sorted(keys, key=lambda k: (k[3], k[4], k)):
        # Equality shares an endpoint price; group it conservatively as well.
        if current and key[3] > right:
            groups.append(current)
            current = []
        current.append(key)
        right = max(right, key[4])
    if current:
        groups.append(current)
    return groups


def _mean(values):
    return fsum(values) / len(values) if values else None


def _difference(primary, baseline):
    return _mean(primary) - _mean(baseline) if primary and baseline else None


def _cost_report(p, b, common, only_p, only_b, differing, cost):
    pv, bv = {k: v - cost for k, v in p.items()}, {k: v - cost for k, v in b.items()}
    shared_sum = fsum(pv[k] for k in sorted(common))
    only_p_sum = fsum(pv[k] for k in sorted(only_p))
    only_b_sum = fsum(bv[k] for k in sorted(only_b))
    parts = None if not p or not b else {
        "common_reweighting": shared_sum * (1 / len(p) - 1 / len(b)),
        "primary_only": only_p_sum / len(p),
        "minus_baseline_only": -only_b_sum / len(b),
    }
    deletions = []
    for group in differing:
        removed = set(group)
        remaining_p = [pv[k] for k in sorted(pv) if k not in removed]
        remaining_b = [bv[k] for k in sorted(bv) if k not in removed]
        deletions.append({
            "start_ts": min(k[3] for k in group), "end_ts": max(k[4] for k in group),
            "primary_labels_removed": len(p) - len(remaining_p),
            "baseline_labels_removed": len(b) - len(remaining_b),
            "mean_difference_bps": _difference(remaining_p, remaining_b),
        })
    differences = [r["mean_difference_bps"] for r in deletions if r["mean_difference_bps"] is not None]
    return {
        "round_trip_cost_bps": cost,
        "primary_mean_net_bps": _mean(list(pv.values())),
        "baseline_mean_net_bps": _mean(list(bv.values())),
        "mean_difference_bps": _difference(list(pv.values()), list(bv.values())),
        "common_payoff_difference_bps": 0.0 if common else None,
        "mean_decomposition_bps": parts,
        "composition_mean_difference_bps": fsum(parts.values()) if parts is not None else None,
        "additive_label_sum_difference_bps": fsum(pv.values()) - fsum(bv.values()),
        "additive_decomposition_bps": {"common": 0.0, "primary_only": only_p_sum,
                                       "minus_baseline_only": -only_b_sum},
        "leave_one_differing_component_out": {
            "comparisons": len(deletions),
            "undefined_comparisons": len(deletions) - len(differences),
            "nonpositive_comparisons": sum(x <= 0 for x in differences),
            "minimum_mean_difference_bps": min(differences, default=None),
            "maximum_mean_difference_bps": max(differences, default=None),
            "deletions": deletions,
        },
    }


def compare_trades(primary, baseline, *, costs=(20, 40, 60)):
    """Reconcile trade identity and arithmetic; never turn counts into power."""
    costs = tuple(_number(c, "cost") for c in costs)
    if not costs or any(c < 0 for c in costs) or len(set(costs)) != len(costs):
        raise ValueError("invalid cost ladder")
    p, b = _indexed(primary), _indexed(baseline)
    common, only_p, only_b = p.keys() & b.keys(), p.keys() - b.keys(), b.keys() - p.keys()
    if any(p[k] != b[k] for k in common):
        raise ValueError("conflicting shared trade gross return")
    groups = _components(p.keys() | b.keys())
    differing = [g for g in groups if any(k in only_p or k in only_b for k in g)]
    result = {
        "primary_labels": len(p), "baseline_labels": len(b),
        "common_labels": len(common), "primary_only_labels": len(only_p),
        "baseline_only_labels": len(only_b), "union_labels": len(p.keys() | b.keys()),
        "temporal_components": len(groups), "differing_temporal_components": len(differing),
        "primary_only_gross_sum_bps": fsum(p[k] for k in sorted(only_p)),
        "baseline_only_gross_sum_bps": fsum(b[k] for k in sorted(only_b)),
        "primary_gross_mean_bps": _mean(list(p.values())),
        "baseline_gross_mean_bps": _mean(list(b.values())),
        "costs": [_cost_report(p, b, common, only_p, only_b, differing, c) for c in costs],
        "interpretation": {
            "unit": "TRADE_LABEL_BPS_NOT_PORTFOLIO_NAV",
            "mean_difference": "Composition contrast, not paired causal alpha; same uniform cost cancels from the two means.",
            "components": "Transitive closed holding intervals across all assets; not proven independent observations.",
            "deletions": "Retrospective influence diagnostic only; never select exclusions, retune, or rescore a strategy from it.",
            "missing_counterfactuals": "Only retained executed labels are compared; missing opportunities are not reconstructed.",
        },
        "authority": {"descriptive_only": True, "new_inferential_test": False,
                      "strategy_admission": False, "promotion": False, "trade": False},
    }
    # Finite inputs alone do not guarantee finite sums/differences.
    def finite_tree(value):
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("nonfinite diagnostic arithmetic")
        if isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        if isinstance(value, list):
            for child in value:
                finite_tree(child)
    finite_tree(result)
    return result


def audit_archive(path):
    """Read only the original consumed evidence, never the adjacent OHLCV cache."""
    raw = Path(path).read_bytes()
    evidence = json.loads(gzip.decompress(raw))
    if (not verify_research_envelope(evidence)
            or evidence["integrity"]["payload_sha256"] != PINNED_PAYLOAD):
        raise ValueError("archive does not match pinned consumed evidence")
    payload, selection = evidence["payload"], evidence["payload"]["selection"]
    if (payload["contract_sha256"] != PINNED_CONTRACT
            or selection["contract_sha256"] != PINNED_CONTRACT
            or selection["fingerprint_id"] != PINNED_FINGERPRINT
            or payload["dataset_manifest"]["normalized_rows_sha256"] != PINNED_DATASET
            or selection["untouched_oos_opened"] is not False
            or selection["genuine_forward_opened"] is not False):
        raise ValueError("pinned evidence identity/authority mismatch")
    segments = {}
    for split in ("train", "validation"):
        arms = {}
        for arm in ("primary", "baseline"):
            arms[arm] = [dict(t, instrument=instrument)
                         for instrument, item in sorted(selection[arm].items())
                         for t in item[split]["trades"]]
        segments[split] = compare_trades(arms["primary"], arms["baseline"])
    return {
        "schema_version": 1,
        "analysis_type": "POST_SELECTION_BASELINE_COMPOSITION_NO_NEW_TEST",
        "fingerprint_id": PINNED_FINGERPRINT,
        "contract_sha256": PINNED_CONTRACT,
        "source_payload_sha256": PINNED_PAYLOAD,
        "source_archive_sha256": hashlib.sha256(raw).hexdigest(),
        "source_dataset_sha256_reference_only_not_read": PINNED_DATASET,
        "source_status_unchanged": "REJECTED_PRE_OOS",
        "source_consumption": "Already-consumed primary/baseline train and validation labels only",
        "protected_dataset_file_read": False,
        "untouched_oos_opened": False, "genuine_forward_opened": False,
        "research_only": True, "trade_authority": False, "promotion_authority": False,
        "causal_inference_authority": False, "new_inferential_test": False,
        "segments": segments,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_archive(args.evidence)
    # Exclusive creation protects retained evidence from accidental overwrite.
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

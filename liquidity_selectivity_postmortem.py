"""Describe archived selection trades; never choose a strategy or open a dataset.

Run: python liquidity_selectivity_postmortem.py --output PATH
This outcome-informed diagnostic cannot provide independent validation evidence.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from pathlib import Path

from research_artifact import verify_research_envelope


EVIDENCE_PATH = Path(__file__).parent / "orchestration/evidence/liquidity_meanrev_001_cache/evidence.json.gz"
SOURCE_SHA256 = "8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e"
HOUR = 3_600_000
BUCKETS = (1, 5, 10, 20, 50, 100)
COSTS = (20, 30, 40, 60)


def _validated(rows):
    result, identities = [], set()
    for row in rows:
        try:
            instrument = row["instrument"]
            if not isinstance(instrument, str) or not instrument:
                raise ValueError("invalid instrument")
            for key in ("shock_return", "trailing_sigma", "gross_bps"):
                value = row[key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f"invalid {key}")
            if row["trailing_sigma"] <= 0:
                raise ValueError("trailing_sigma must be positive")
            for key in ("signal_ts", "entry_ts", "exit_ts"):
                if type(row[key]) is not int or row[key] < 0 or row[key] % HOUR:
                    raise ValueError("invalid hourly timestamp")
            if row["entry_ts"] != row["signal_ts"] + HOUR or row["exit_ts"] != row["entry_ts"] + 6 * HOUR:
                raise ValueError("noncausal or changed frozen holding interval")
            identity = (instrument, row["signal_ts"])
            if identity in identities:
                raise ValueError("duplicate trade identity")
            identities.add(identity)
            score = abs(row["shock_return"]) / row["trailing_sigma"]
            if not math.isfinite(score):
                raise ValueError("nonfinite score")
            result.append(dict(row, score=score))
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError("malformed selection trade") from exc
    return sorted(result, key=lambda row: (row["signal_ts"], row["instrument"]))


def _metrics(rows, total):
    clusters, until = 0, -1
    for row in rows:
        if row["entry_ts"] >= until:
            clusters += 1
        until = max(until, row["exit_ts"])
    gross = [row["gross_bps"] for row in rows]
    return {
        "trade_labels": len(rows),
        "coverage_fraction": len(rows) / total if total else None,
        "distinct_signal_hours": len({row["signal_ts"] for row in rows}),
        "holding_interval_clusters": clusters,
        "mean_gross_bps": statistics.mean(gross) if gross else None,
        "costs_bps": {
            str(cost): {
                "mean_net_bps": statistics.mean(gross) - cost if gross else None,
                "win_fraction": sum(value > cost for value in gross) / len(gross) if gross else None,
            } for cost in COSTS
        },
    }


def summarize(train, validation):
    """Training-only empirical cutoffs, inclusive ties; full baseline has no cutoff."""
    train, validation = _validated(train), _validated(validation)
    if not train:
        raise ValueError("training trades are required")
    if validation and max(row["exit_ts"] for row in train) >= min(row["signal_ts"] for row in validation):
        raise ValueError("training/validation chronology overlaps")
    scores = sorted((row["score"] for row in train), reverse=True)
    result = {}
    for percent in BUCKETS:
        cutoff = scores[math.ceil(len(scores) * percent / 100) - 1] if percent < 100 else None
        result[str(percent)] = {"training_score_cutoff": cutoff}
        for name, rows in (("train", train), ("validation", validation)):
            chosen = [row for row in rows if cutoff is None or row["score"] >= cutoff]
            result[str(percent)][name] = _metrics(chosen, len(rows))
    return result


def build_report(path=EVIDENCE_PATH):
    """Read only the pinned original evidence envelope, never the market dataset."""
    envelope = json.loads(gzip.decompress(path.read_bytes()))
    if not verify_research_envelope(envelope) or envelope["integrity"]["payload_sha256"] != SOURCE_SHA256:
        raise ValueError("original sealed evidence identity mismatch")
    selection = envelope["payload"]["selection"]
    segments, bounds = {}, {}
    for segment in ("train", "validation"):
        rows, starts, ends = [], [], []
        for instrument, source in selection["primary"].items():
            cell = source[segment]
            start, end = cell["start_ts"], cell["end_ts"] + HOUR
            starts.append(start)
            ends.append(end)
            for row in cell["trades"]:
                if not start <= row["signal_ts"] < row["exit_ts"] < end:
                    raise ValueError("trade outside frozen selection interval")
                rows.append(dict(row, instrument=instrument))
        segments[segment] = rows
        bounds[segment] = {"start_inclusive_ms": min(starts), "end_exclusive_ms": max(ends)}
    return {
        "schema_version": 1,
        "analysis_type": "POST_SELECTION_DESCRIPTIVE_NO_INDEPENDENT_CONFIRMATION",
        "fingerprint_id": selection["fingerprint_id"],
        "contract_sha256": selection["contract_sha256"],
        "source_payload_sha256": SOURCE_SHA256,
        "source_run_id": 35420353644,
        "strategy_status": "REJECTED_UNCHANGED",
        "research_only": True,
        "promotion_authority": False,
        "trade_authority": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "score": "abs(shock_return) / trailing_sigma; formation-time intensity, not calibrated confidence",
        "cutoff_method": "Top ceil(train_count * percent / 100) training scores; include all ties; apply same cutoff to validation. 100% means all labels.",
        "limitations": [
            "Both original training and validation outcomes were observed before this diagnostic; no new hypothesis test or survival gate.",
            "Buckets are nested and dependent. No best bucket is selected and no multiplicity-adjusted significance is claimed.",
            "Holding-interval clusters use half-open [entry, exit) intervals across assets; even disjoint clusters are not proven independent.",
            "Equal-weight trade-label bps are not portfolio returns. Frozen cost proxies are not observed execution costs.",
            "Subsets contain only originally executed labels. Filtering could change subsequent entry eligibility; no selective strategy is replayed.",
            "Small and empty buckets cannot establish reliable selectivity; null means unavailable, not zero.",
            "A stronger shock is not necessarily a stronger edge. No expected-return, uncertainty, liquidity or capacity model is fitted.",
        ],
        "selection_intervals": bounds,
        "buckets": summarize(segments["train"], segments["validation"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(build_report(), indent=2, allow_nan=False) + "\n", encoding="utf-8")

"""Research-only 2x+ event/cohort construction. No forecast or trade authority."""
from collections import defaultdict

from .core import (TARGET, digest, iso, label_snapshot, prepare_bars,
                   prepare_snapshots, timestamp, validate_contract)
from .matching import attach_controls, build_pools

__all__ = ["build_dataset", "digest"]


def build_dataset(contract, snapshots, bars, *, as_of, expected_contract_hash):
    validate_contract(contract, expected_contract_hash)
    now = timestamp(as_of)
    snapshots = prepare_snapshots(contract, snapshots, now)
    # This function cannot access future bar/outcome data; hash its result first.
    pools = build_pools(contract, snapshots)
    pool_hash = digest(pools)
    bars = prepare_bars(contract, bars)
    by_market = defaultdict(list)
    for bar in bars:
        by_market[(bar["asset_id"], bar["venue"])].append(bar)
    labels = [label_snapshot(contract, row, by_market[(row["asset_id"], row["venue"])], now)
              for row in snapshots if row["eligible"]]
    cases, controls = attach_controls(contract, pools, labels)
    complete = sum(row["status"] == "COMPLETE" for row in labels)
    events = sum(row["reached_2x"] is True for row in labels)
    censored = len(labels)-complete
    hashes = {"contract": digest(contract), "snapshots": digest(snapshots), "bars": digest(bars),
              "matching_pools": pool_hash, "labels": digest(labels), "controls": digest(controls),
              "cases": digest(cases)}
    summary = {"eligible_count": len(labels), "excluded_count": len(snapshots)-len(labels),
                        "complete_count": complete, "censored_count": censored, "event_count": events,
                        "matched_case_count": sum(row["status"] == "MATCHED" for row in cases),
                        "control_pair_count": len(controls), "unique_control_count": len({r["control_id"] for r in controls}),
                        "complete_cohort_base_rate": events/complete if complete else None,
                        "full_cohort_base_rate": events/complete if complete and not censored else None,
                        "base_rate_warning": "Complete-case rate may be survival-biased when any outcomes are censored; matched-pair rates are not population rates.",
                        "independence_warning": "Same-asset overlap removed; controls can be reused and cross-asset/date dependence requires clustered inference.",
                        "input_provenance_status": "DECLARED_NOT_INDEPENDENTLY_AUDITED",
                        "prediction_status": "RESEARCH_ONLY", "trade_authority": False,
                        "broker_connected": False, "untouched_oos_opened": False}
    hashes["summary"] = digest(summary)
    return {"schema_version": 1, "target": TARGET, "as_of": iso(now), "hashes": hashes,
            "dataset_hash": digest({"hashes": hashes, "as_of": iso(now)}),
            "snapshots": snapshots, "matching_pools": pools, "labels": labels,
            "cases": cases, "controls": controls, "summary": summary}

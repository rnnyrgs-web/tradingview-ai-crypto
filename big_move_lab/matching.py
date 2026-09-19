"""Match pre-event covariates first; attach outcome classifications only afterward."""
from collections import Counter, defaultdict

from .core import NUMERIC_MATCH


def build_pools(contract, snapshots):
    strata = defaultdict(list)
    for row in snapshots:
        if row["eligible"]:
            key = (row["decision_time"], row["venue"], row["features"]["sector"], row["features"]["regime"])
            strata[key].append(row)
    pools = []
    for members in strata.values():
        for case in members:
            neighbors = []
            for control in members:
                if case["asset_id"] == control["asset_id"]:
                    continue
                distances = [abs(case["features"][k]-control["features"][k])/contract["calipers"][k]
                             for k in NUMERIC_MATCH]
                if all(d <= 1 for d in distances):
                    neighbors.append((sum(distances), control["asset_id"], control["snapshot_id"]))
            for rank, (distance, asset, sid) in enumerate(sorted(neighbors)[:contract["neighbor_pool_size"]], 1):
                pools.append({"snapshot_id": case["snapshot_id"], "neighbor_id": sid,
                              "neighbor_asset_id": asset, "rank": rank, "distance": distance})
    return sorted(pools, key=lambda r: (r["snapshot_id"], r["rank"]))


def attach_controls(contract, pools, labels):
    by_id = {row["snapshot_id"]: row for row in labels}
    grouped = defaultdict(list)
    for row in pools:
        grouped[row["snapshot_id"]].append(row)
    cases, controls = [], []
    for case in labels:
        if case["reached_2x"] is not True:
            continue
        selected, unknown, winners = [], 0, 0
        for neighbor in grouped[case["snapshot_id"]]:
            label = by_id[neighbor["neighbor_id"]]
            if label["reached_2x"] is False:
                selected.append({"case_id": case["snapshot_id"], "case_asset_id": case["asset_id"],
                                 "control_id": label["snapshot_id"], "control_asset_id": label["asset_id"],
                                 "decision_time": case["decision_time"], "rank": neighbor["rank"],
                                 "distance": neighbor["distance"]})
            elif label["reached_2x"] is None:
                unknown += 1
            else:
                winners += 1
        status = "MATCHED" if len(selected) >= contract["min_controls"] else "INSUFFICIENT_CONTROLS"
        cases.append({"snapshot_id": case["snapshot_id"], "asset_id": case["asset_id"],
                      "status": status, "control_count": len(selected),
                      "unknown_neighbor_count": unknown, "winner_neighbor_count": winners})
        controls.extend({**row, "case_status": status} for row in selected)
    reused = Counter(row["control_id"] for row in controls)
    for row in controls:
        row["control_reuse_count"] = reused[row["control_id"]]
    return cases, controls

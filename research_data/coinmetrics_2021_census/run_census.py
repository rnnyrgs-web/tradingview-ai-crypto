"""One fixed historical source-coverage census. Never opens 2x outcomes.

Run with --acquire once, then without it to reproduce from retained raw bytes.
This script is offline by default and cannot admit source evidence to Cohort 001.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
METRICS = ("CapMrktCurUSD", "SplyCur")
COMMIT = "25e3b1d90ffddef11c1663f8fa43696f60bc8061"
TREE = "c0c58a48402cb33032c6c3f00402cb50e1923fd8"
CUTOFF = "2021-01-04T00:00:00Z"


def summarize(raw, expected_blob, decision_at):
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw,
                        usedforsecurity=False).hexdigest()
    if blob != expected_blob:
        raise ValueError("upstream Git blob mismatch")
    cutoff = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))
    header = next(reader)
    if len(header) != len(set(header)) or header.count("time") != 1:
        raise ValueError("invalid header")
    time_index = header.index("time")
    indices = {m: header.index(m) for m in METRICS if m in header}
    prior = None
    latest = None
    latest_metrics = None
    pair_rows = pre_rows = excluded_rows = 0
    positive_rows = Counter()
    for row in reader:
        if len(row) != len(header):
            raise ValueError("ragged row")
        date_text = row[time_index]
        # The fixed provider CSV uses UTC calendar dates, no timezone heuristics.
        date = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if prior is not None and date <= prior:
            raise ValueError("duplicate or non-chronological row")
        prior = date
        if date >= cutoff:
            excluded_rows += 1
            continue
        pre_rows += 1
        metrics = {}
        for metric in METRICS:
            if metric not in indices:
                metrics[metric] = {"status": "MISSING_COLUMN", "value": None}
                continue
            value = row[indices[metric]]
            if not value:
                metrics[metric] = {"status": "MISSING_VALUE", "value": None}
                continue
            try:
                number = Decimal(value)
                valid = number.is_finite() and number > 0
            except InvalidOperation:
                valid = False
            metrics[metric] = {"status": "POSITIVE" if valid else "INVALID_VALUE",
                               "value": value if valid else None}
            positive_rows[metric] += int(valid)
        pair_rows += int(all(metrics[m]["status"] == "POSITIVE" for m in METRICS))
        latest = date
        latest_metrics = metrics
    age = (cutoff - latest).total_seconds() / 3600 if latest else None
    return {
        "git_blob_sha1": blob,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "metric_columns": {m: m in indices for m in METRICS},
        "pre_cutoff_rows": pre_rows,
        "at_or_after_cutoff_rows": excluded_rows,
        "positive_rows": {m: positive_rows[m] for m in METRICS},
        "positive_pair_rows": pair_rows,
        "latest_pre_cutoff_row": latest.date().isoformat() if latest else None,
        "latest_row_age_hours": age,
        "latest_metrics": latest_metrics,
        "fresh_latest_pair": bool(latest_metrics and age <= 72 and
                                  all(latest_metrics[m]["status"] == "POSITIVE" for m in METRICS)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    manifest_bytes = (ROOT / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    tree = json.loads((ROOT / "upstream_tree.json").read_text())
    commit = json.loads((ROOT / "upstream_commit.json").read_text())
    if not manifest["source_commit"] == commit["sha"] == COMMIT:
        raise ValueError("source commit mismatch")
    if not manifest["source_tree"] == commit["tree"]["sha"] == tree["sha"] == TREE:
        raise ValueError("source tree mismatch")
    if tree["truncated"] is not False or manifest["decision_at"] != CUTOFF:
        raise ValueError("truncated tree or cutoff mismatch")
    expected = [f for f in tree["tree"] if f["type"] == "blob" and
                f["path"].startswith("csv/") and f["path"].endswith(".csv") and
                f["path"] != "csv/metrics.csv"]
    if manifest["files"] != expected or len(expected) != 100:
        raise ValueError("frozen denominator mismatch")
    raw_dir = ROOT / "raw"
    raw_dir.mkdir(exist_ok=True)

    def process(item):
        symbol = Path(item["path"]).stem
        path = raw_dir / (symbol + ".csv.gz")
        url = f"https://raw.githubusercontent.com/coinmetrics/data/{COMMIT}/{item['path']}"
        try:
            if path.exists():
                raw = gzip.decompress(path.read_bytes())
            elif args.acquire:
                with urllib.request.urlopen(url, timeout=45) as response:  # nosec B310: fixed HTTPS source
                    raw = response.read(16000000)
            else:
                raise ValueError("raw artifact missing; use --acquire explicitly")
            if len(raw) != item["size"]:
                raise ValueError("upstream size mismatch")
            result = summarize(raw, item["sha"], CUTOFF)
            if not path.exists():
                path.write_bytes(gzip.compress(raw, mtime=0))
            return {"source_symbol": symbol, "source_path": item["path"], "source_url": url,
                    "status": "VERIFIED_BLOB_COVERAGE_ONLY", **result}
        except (OSError, ValueError, csv.Error, EOFError, StopIteration) as exc:
            return {"source_symbol": symbol, "source_path": item["path"], "source_url": url,
                    "status": "ACQUISITION_OR_PARSE_FAILED", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(process, expected))
    valid = [r for r in results if r["status"] == "VERIFIED_BLOB_COVERAGE_ONLY"]
    summary = {
        "source_files_frozen": len(expected), "verified_blobs": len(valid),
        "failed_blobs": len(results) - len(valid),
        "raw_bytes": sum(r["raw_bytes"] for r in valid),
        "pre_cutoff_source_daily_rows": sum(r["pre_cutoff_rows"] for r in valid),
        "at_or_after_cutoff_rows_excluded": sum(r["at_or_after_cutoff_rows"] for r in valid),
        "positive_pair_source_daily_rows": sum(r["positive_pair_rows"] for r in valid),
        "files_with_both_columns": sum(all(r["metric_columns"].values()) for r in valid),
        "fresh_latest_positive_pairs": sum(r["fresh_latest_pair"] for r in valid),
        "latest_row_status_by_metric": {m: dict(Counter(
            r["latest_metrics"][m]["status"] if r["latest_metrics"] else "NO_PRE_CUTOFF_ROW"
            for r in valid)) for m in METRICS},
        "stale_latest_rows_gt_72h": sum(r["latest_row_age_hours"] is not None and
                                         r["latest_row_age_hours"] > 72 for r in valid),
        "canonical_cohort_eligible_snapshots": 0,
        "historical_2x_events": 0, "matched_controls": 0,
        "precursor_hypotheses_tested": 0, "prospective_candidates": 0,
    }
    output = {
        "issue": 812, "classification": "EMPIRICAL_SOURCE_COVERAGE_ONLY",
        "source_commit": COMMIT, "source_tree": TREE, "decision_at": CUTOFF,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "parser_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "summary": summary, "records": results,
        "limitations": [
            "Unsigned upstream commit time is not authenticated public availability time.",
            "Source symbols are not canonical asset identities or Binance historical members.",
            "Daily rows are not independent events or point-in-time decision snapshots.",
            "Only one historical vintage is measured; earlier daily rows may be revised.",
            "Stablecoins, wrappers, obsolete symbols and potential duplicate exposures are retained.",
            "No source-symbol disappearance is classified as delisting or non-winner.",
            "Supply semantics, historical identity, sector, membership, liquidity and depth remain unqualified.",
        ],
        "outcomes_opened": False, "cohort_admission": False,
        "protected_oos_opened": False, "broker_connected": False, "trade_authority": False,
    }
    (ROOT / "results.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))
    if summary["failed_blobs"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

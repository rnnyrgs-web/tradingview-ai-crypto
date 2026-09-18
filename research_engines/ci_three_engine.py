"""CI/runtime proof that all three research engines execute one frozen path."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .lean_adapter import run_lean_project
from .lean_fixture import build_fixture
from .nautilus_adapter import run_nautilus
from .protocol import reconcile
from .vectorbt_adapter import run_vectorbt


def run_three_engine_fixture(
    *,
    spy_zip,
    launcher_dll,
    lean_config,
    algorithm_dll,
    data_folder,
    work_dir,
):
    fixture = build_fixture(spy_zip)
    contract = fixture["contract"]
    bars = fixture["bars"]
    entries = fixture["entries"]
    exits = fixture["exits"]

    work = Path(work_dir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    evidence_path = work / "lean-normalized-evidence.json"
    results_dir = work / "lean-results"
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "config": str(Path(lean_config).expanduser().resolve(strict=True)),
        "algorithm-type-name": "FrozenPathResearchAlgorithm",
        "algorithm-language": "CSharp",
        "algorithm-location": str(
            Path(algorithm_dll).expanduser().resolve(strict=True)
        ),
        "data-folder": str(Path(data_folder).expanduser().resolve(strict=True)),
        "results-destination-folder": str(results_dir),
        "backtest-name": "cross-engine-frozen-path",
        "close-automatically": True,
    }
    (work / "lean_args.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    frozen = contract.canonical()
    os.environ["LEAN_LAUNCHER_DLL"] = str(
        Path(launcher_dll).expanduser().resolve(strict=True)
    )
    os.environ["LEAN_CONTRACT_FINGERPRINT"] = contract.fingerprint()
    os.environ["LEAN_EVIDENCE_PATH"] = str(evidence_path)
    os.environ["LEAN_VALIDATION_INITIAL_CAPITAL"] = str(
        frozen["validation_initial_capital"]
    )
    os.environ["LEAN_VALIDATION_QUANTITY"] = str(frozen["validation_quantity"])

    vector = run_vectorbt(contract, bars, entries, exits)
    nautilus = run_nautilus(contract, bars, entries, exits)
    lean = run_lean_project(contract, work, evidence_path)

    result = reconcile(
        {"vectorbt": vector, "nautilus": nautilus, "lean": lean},
        required=("vectorbt", "nautilus", "lean"),
        price_tolerance=1e-6,
        pnl_tolerance=1e-6,
        metric_tolerance=1e-6,
        expected_contract_fingerprint=contract.fingerprint(),
    )
    report = {
        "contract_fingerprint": contract.fingerprint(),
        "contract": frozen,
        "bars": len(bars),
        "vectorbt": vector,
        "nautilus": nautilus,
        "lean": lean,
        "reconciliation": result,
    }
    (work / "three-engine-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    if not result["ok"]:
        raise RuntimeError(
            "three-engine frozen-path reconciliation failed: "
            + json.dumps(result, sort_keys=True)
        )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spy-zip", required=True)
    parser.add_argument("--launcher-dll", required=True)
    parser.add_argument("--lean-config", required=True)
    parser.add_argument("--algorithm-dll", required=True)
    parser.add_argument("--data-folder", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    report = run_three_engine_fixture(
        spy_zip=args.spy_zip,
        launcher_dll=args.launcher_dll,
        lean_config=args.lean_config,
        algorithm_dll=args.algorithm_dll,
        data_folder=args.data_folder,
        work_dir=args.work_dir,
    )
    print(json.dumps(report["reconciliation"], indent=2))


if __name__ == "__main__":
    main()

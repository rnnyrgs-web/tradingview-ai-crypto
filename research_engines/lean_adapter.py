"""LEAN validation adapter.

Supports either the LEAN CLI or a directly source-built
QuantConnect.Lean.Launcher.dll. Process success alone never counts as research
proof: normalized evidence carrying the exact frozen contract fingerprint is
required after execution.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404 -- fixed resolved executable/argv only; shell is never used.
from pathlib import Path

from .availability import lean_runtime
from .evidence import evidence


_SOURCE_ARG_ORDER = (
    "config",
    "algorithm-type-name",
    "algorithm-language",
    "algorithm-location",
    "data-folder",
    "results-destination-folder",
    "transaction-log",
    "backtest-name",
    "close-automatically",
)


def lean_available():
    return lean_runtime()["available"]


def write_lean_contract(contract, destination):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": contract.canonical(),
        "contract_fingerprint": contract.fingerprint(),
        "research_only": True,
        "trade_authority": False,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _source_launcher_argv(runtime, project):
    manifest_path = project / "lean_args.json"
    if not manifest_path.is_file():
        raise RuntimeError("source-built LEAN project is missing lean_args.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("LEAN launch manifest must be an object")
    unknown = sorted(set(manifest) - set(_SOURCE_ARG_ORDER))
    if unknown:
        raise RuntimeError(
            "LEAN launch manifest contains unsupported arguments: "
            + ", ".join(unknown)
        )

    required = {
        "config",
        "algorithm-type-name",
        "algorithm-language",
        "algorithm-location",
        "data-folder",
    }
    missing = sorted(key for key in required if not str(manifest.get(key) or "").strip())
    if missing:
        raise RuntimeError(
            "LEAN launch manifest missing required arguments: " + ", ".join(missing)
        )

    launcher = Path(runtime["launcher_dll"]).resolve(strict=True)
    argv = [runtime["executable"], str(launcher)]
    for key in _SOURCE_ARG_ORDER:
        if key not in manifest:
            continue
        value = manifest[key]
        if isinstance(value, bool):
            value = "true" if value else "false"
        text = str(value).strip()
        if not text:
            continue
        argv.extend([f"--{key}", text])
    return launcher, argv


def _normalized_evidence(contract, result_file, initial_capital):
    result = Path(result_file).expanduser().resolve()
    if not result.is_file():
        raise RuntimeError("LEAN did not produce normalized result evidence")
    payload = json.loads(result.read_text(encoding="utf-8"))
    if (
        payload.get("contract_fingerprint") != contract.fingerprint()
        or payload.get("executed") is not True
    ):
        raise RuntimeError("LEAN result does not prove execution of frozen contract")
    if not isinstance(payload.get("trades"), list):
        raise RuntimeError("LEAN result has no normalized trades")
    out = evidence("lean", contract, payload["trades"], initial_capital)
    out["execution_mode"] = str(payload.get("execution_mode") or "lean_backtest")
    return out


def run_lean_project(
    contract,
    project_dir,
    result_file,
    timeout_seconds=1800,
    initial_capital=None,
):
    runtime = lean_runtime()
    if not runtime["available"]:
        raise RuntimeError(
            "LEAN unavailable; configure CLI or LEAN_LAUNCHER_DLL with dotnet"
        )

    project = Path(project_dir).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError("LEAN project path must be an existing directory")

    frozen = contract.canonical()
    capital = float(frozen["validation_initial_capital"])
    if initial_capital is not None and abs(float(initial_capital) - capital) > 1e-9:
        raise ValueError("LEAN adapter capital disagrees with frozen contract")
    if frozen["execution_price_model"] != "bar_close_after_lag":
        raise ValueError("LEAN execution price model disagrees with frozen contract")
    if frozen["timestamp_unit"] != "ns":
        raise ValueError("LEAN timestamp convention disagrees with frozen contract")

    timeout = int(timeout_seconds)
    if timeout < 1 or timeout > 3600:
        raise ValueError("LEAN timeout must be between 1 and 3600 seconds")

    if runtime["mode"] == "cli":
        argv = [runtime["executable"], "backtest", str(project)]
        cwd = project
        execution_mode = "lean_cli_backtest"
    elif runtime["mode"] == "source_launcher":
        launcher, argv = _source_launcher_argv(runtime, project)
        cwd = launcher.parent
        execution_mode = "lean_source_launcher"
    else:
        raise RuntimeError("unsupported LEAN runtime mode")

    proc = subprocess.run(  # nosec B603 -- fixed executable/whitelisted argv, no shell.
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-3000:]
        raise RuntimeError(f"LEAN local backtest failed: {tail}")

    out = _normalized_evidence(contract, result_file, capital)
    out["execution_mode"] = execution_mode
    out["decision_lag_bars"] = int(frozen["decision_lag_bars"])
    out["validation_quantity"] = float(frozen["validation_quantity"])
    return out

"""LEAN validation adapter.

The adapter supports either the LEAN CLI or a directly source-built
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
    initial_capital=100000.0,
):
    """Execute a frozen LEAN project using CLI or source-built Launcher.

    For source-launcher mode the project must prepare the Launcher's config.json
    and algorithm artifacts before this function is called. The launcher is run
    from its own directory so LEAN resolves assemblies/config naturally.
    """
    runtime = lean_runtime()
    if not runtime["available"]:
        raise RuntimeError(
            "LEAN unavailable; configure CLI or LEAN_LAUNCHER_DLL with dotnet"
        )

    project = Path(project_dir).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError("LEAN project path must be an existing directory")

    timeout = int(timeout_seconds)
    if timeout < 1 or timeout > 3600:
        raise ValueError("LEAN timeout must be between 1 and 3600 seconds")

    if runtime["mode"] == "cli":
        argv = [runtime["executable"], "backtest", str(project)]
        cwd = project
        execution_mode = "lean_cli_backtest"
    elif runtime["mode"] == "source_launcher":
        launcher = Path(runtime["launcher_dll"]).resolve(strict=True)
        argv = [runtime["executable"], str(launcher)]
        cwd = launcher.parent
        execution_mode = "lean_source_launcher"
    else:
        raise RuntimeError("unsupported LEAN runtime mode")

    proc = subprocess.run(  # nosec B603 -- fixed executable/argv, no shell, validated local paths.
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise RuntimeError(f"LEAN local backtest failed: {tail}")

    out = _normalized_evidence(contract, result_file, initial_capital)
    out["execution_mode"] = execution_mode
    return out

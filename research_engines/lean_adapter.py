"""LEAN local CLI validation adapter.

A successful process alone is insufficient: the project must emit normalized
trade evidence carrying the exact frozen contract fingerprint.
"""
from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 -- fixed resolved executable/argv only; shell is never used.
from pathlib import Path

from .evidence import evidence


def lean_executable():
    return shutil.which("lean")


def lean_available():
    return lean_executable() is not None


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


def run_lean_project(
    contract,
    project_dir,
    result_file,
    timeout_seconds=1800,
    initial_capital=100000.0,
):
    executable = lean_executable()
    if executable is None:
        raise RuntimeError("LEAN CLI unavailable")

    project = Path(project_dir).expanduser().resolve(strict=True)
    result = Path(result_file).expanduser().resolve()
    if not project.is_dir():
        raise ValueError("LEAN project path must be an existing directory")

    timeout = int(timeout_seconds)
    if timeout < 1 or timeout > 3600:
        raise ValueError("LEAN timeout must be between 1 and 3600 seconds")

    proc = subprocess.run(  # nosec B603 -- fixed executable/argv, no shell, validated project path.
        [executable, "backtest", str(project)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("LEAN local backtest failed")
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
    out["execution_mode"] = "lean_local_backtest"
    return out

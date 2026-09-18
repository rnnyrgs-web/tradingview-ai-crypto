"""LEAN/QuantConnect local validation adapter.

Process execution is restricted to the resolved LEAN executable and a validated
local project directory. No shell is used and no arbitrary command is accepted.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 -- fixed argv to a resolved trusted executable; shell is never used.
from pathlib import Path


def lean_executable() -> str | None:
    return shutil.which("lean")


def lean_available() -> bool:
    return lean_executable() is not None


def write_lean_contract(contract, destination) -> str:
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


def run_lean_project(project_dir, timeout_seconds=1800) -> dict:
    executable = lean_executable()
    if executable is None:
        raise RuntimeError("LEAN CLI unavailable; install/configure it in the research environment")
    project = Path(project_dir).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError("LEAN project path must be an existing directory")
    timeout = int(timeout_seconds)
    if timeout < 1 or timeout > 3600:
        raise ValueError("LEAN timeout must be between 1 and 3600 seconds")
    proc = subprocess.run(  # nosec B603 -- fixed executable/argv, no shell, validated local directory.
        [executable, "backtest", str(project)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return {
        "ok": proc.returncode == 0,
        "engine": "lean",
        "returncode": proc.returncode,
        "research_only": True,
        "trade_authority": False,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }

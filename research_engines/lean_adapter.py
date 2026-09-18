"""LEAN/QuantConnect local validation adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def lean_available() -> bool:
    return shutil.which("lean") is not None


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
    if not lean_available():
        raise RuntimeError("LEAN CLI unavailable; install/configure it in the research environment")
    proc = subprocess.run(
        ["lean", "backtest", str(project_dir)],
        capture_output=True,
        text=True,
        timeout=int(timeout_seconds),
        check=False,
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

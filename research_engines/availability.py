"""Research engine capability detection.

These adapters never grant trading, paper-ledger, promotion, or broker authority.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

ENGINE_MODULES = {"vectorbt": "vectorbt", "nautilus": "nautilus_trader"}


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def lean_runtime() -> dict:
    """Resolve either the LEAN CLI or a source-built Launcher DLL."""
    cli = shutil.which("lean")
    if cli:
        return {
            "available": True,
            "mode": "cli",
            "executable": cli,
            "launcher_dll": None,
            "dotnet": None,
        }

    launcher_raw = str(os.getenv("LEAN_LAUNCHER_DLL") or "").strip()
    launcher = Path(launcher_raw).expanduser() if launcher_raw else None
    dotnet = shutil.which(str(os.getenv("DOTNET_EXE") or "dotnet"))
    if launcher is not None and launcher.is_file() and dotnet:
        return {
            "available": True,
            "mode": "source_launcher",
            "executable": dotnet,
            "launcher_dll": str(launcher.resolve()),
            "dotnet": dotnet,
        }

    return {
        "available": False,
        "mode": None,
        "executable": None,
        "launcher_dll": str(launcher) if launcher else None,
        "dotnet": dotnet,
    }


def engine_availability() -> dict:
    engines = {
        name: {
            "available": _installed(module),
            "module": module,
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
        }
        for name, module in ENGINE_MODULES.items()
    }
    lean = lean_runtime()
    engines["lean"] = {
        "available": lean["available"],
        "module": None,
        "executable": lean["executable"],
        "launcher_dll": lean["launcher_dll"],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "configuration": lean["mode"] or "lean_cli_or_source_launcher_required",
    }
    return engines


def require_engine(name: str) -> dict:
    key = str(name or "").strip().lower()
    state = engine_availability()
    if key not in state:
        raise ValueError(f"unsupported research engine: {key}")
    if not state[key]["available"]:
        raise RuntimeError(f"research engine unavailable: {key}")
    return state[key]

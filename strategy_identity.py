"""Deterministic identity for research code allowed to reach production."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config import BACKTEST_COST_BPS, HORIZONS, STRATEGY_VERSION


ROOT = Path(__file__).resolve().parent
IDENTITY_SOURCE_FILES = (
    "backtest.py",
    "features.py",
    "strategy_families.py",
)
FAMILY_ALIASES = {"relative_strength_btc": "relative_strength"}


def normalize_family(value: str) -> str:
    family = str(value or "").strip().lower()
    return FAMILY_ALIASES.get(family, family)


def research_code_sha256() -> str:
    digest = hashlib.sha256()
    for name in IDENTITY_SOURCE_FILES:
        path = ROOT / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_strategy_identity(symbol: str, horizon: str, strategy_family: str) -> dict:
    normalized_horizon = str(horizon or "").strip()
    family = normalize_family(strategy_family)
    bars = tuple(HORIZONS.get(normalized_horizon, {}).get("bars", ()))
    identity = {
        "symbol": str(symbol or "").strip().upper(),
        "production_horizon": normalized_horizon,
        "strategy_family": family,
        "timeframes": list(bars),
        "strategy_version": STRATEGY_VERSION,
        "backtest_cost_bps": float(BACKTEST_COST_BPS),
        "research_code_sha256": research_code_sha256(),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    identity["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return identity

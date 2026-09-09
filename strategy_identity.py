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
    "robustness.py",
    "strategy_families.py",
    "strategy_identity.py",
)
FAMILY_ALIASES = {"relative_strength_btc": "relative_strength"}
SUPPORTED_STRATEGY_FAMILIES = frozenset({
    "trend",
    "breakout",
    "momentum",
    "mean_reversion",
    "volatility_expansion",
    "relative_strength",
})


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
    normalized_symbol = str(symbol or "").strip().upper()
    normalized_horizon = str(horizon or "").strip()
    family = normalize_family(strategy_family)
    bars = tuple(HORIZONS.get(normalized_horizon, {}).get("bars", ()))
    identity_complete = bool(
        normalized_symbol
        and bars
        and family in SUPPORTED_STRATEGY_FAMILIES
    )
    identity = {
        "symbol": normalized_symbol,
        "production_horizon": normalized_horizon,
        "strategy_family": family,
        "timeframes": list(bars),
        "strategy_version": STRATEGY_VERSION,
        "backtest_cost_bps": float(BACKTEST_COST_BPS),
        "research_code_sha256": research_code_sha256(),
        "identity_complete": identity_complete,
    }
    if identity_complete:
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        identity["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    else:
        # Missing/unsupported strategy attribution must never look like a valid
        # immutable strategy fingerprint or accumulate genuine-forward proof.
        identity["fingerprint"] = ""
    return identity

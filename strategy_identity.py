"""Deterministic identity for research code allowed to reach production."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config import BACKTEST_COST_BPS, HORIZONS, STRATEGY_VERSION
from strategy_contract import CONTRACT_SCHEMA_VERSION, StrategyContract


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


def build_strategy_identity(
    symbol: str,
    horizon: str,
    strategy_family: str,
    *,
    contract: dict | None = None,
) -> dict:
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

    if contract is not None:
        strategy_contract = StrategyContract.from_mapping(contract)
        contract_payload = strategy_contract.canonical_payload()
        contract_family = normalize_family(contract_payload["strategy_family"])
        contract_horizon = str(contract_payload["horizon"]).strip()
        if contract_family != family:
            raise ValueError("strategy contract family does not match strategy identity")
        if contract_horizon != normalized_horizon:
            raise ValueError("strategy contract horizon does not match strategy identity")
        identity["contract_schema_version"] = CONTRACT_SCHEMA_VERSION
        identity["fingerprint"] = strategy_contract.fingerprint() if identity_complete else ""
        identity["dataset_id"] = contract_payload["dataset_id"]
        identity["dataset_sha256"] = contract_payload["dataset_sha256"]
        identity["hypothesis_id"] = contract_payload["hypothesis_id"]
        identity["experiment_id"] = contract_payload["experiment_id"]
        return identity

    if identity_complete:
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        identity["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    else:
        # Missing or unsupported strategy attribution must never look like a
        # valid immutable strategy fingerprint or accumulate forward proof.
        identity["fingerprint"] = ""
    return identity

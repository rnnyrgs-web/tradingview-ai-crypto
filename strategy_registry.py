"""Deterministic, fail-closed identities for backtested strategies.

This module only constructs identities. It does not approve or promote a
strategy and intentionally contains no live registry entries.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from strategy_families import STRATEGY_FAMILIES


_IDENTITY_VERSION = "strategy-identity-v1"
_SUPPORTED_HORIZONS = frozenset({"15m", "1H", "4H", "1D", "24h", "7d"})
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}-USDT(?:-SWAP)?$")
_PARAMETER_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _canonical_rule_value(value: Any, *, path: str, ancestors: set[int]) -> Any:
    """Return a JSON-safe rule value or reject it without coercion."""
    if value is None:
        raise ValueError(f"{path} must not be null")
    if type(value) is bool or type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite")
        return value
    if type(value) is str:
        if not value or value != value.strip():
            raise ValueError(f"{path} must be a non-empty, trimmed string")
        return value

    if type(value) in (dict, list):
        object_id = id(value)
        if object_id in ancestors:
            raise ValueError(f"{path} must not contain a cycle")
        next_ancestors = ancestors | {object_id}

        if type(value) is list:
            if not value:
                raise ValueError(f"{path} must not be an empty list")
            return [
                _canonical_rule_value(item, path=f"{path}[{index}]", ancestors=next_ancestors)
                for index, item in enumerate(value)
            ]

        if not value:
            raise ValueError(f"{path} must not be an empty mapping")
        canonical = {}
        for key, item in value.items():
            if type(key) is not str or not _PARAMETER_NAME_RE.fullmatch(key):
                raise ValueError(f"{path} contains an invalid parameter name")
            canonical[key] = _canonical_rule_value(
                item, path=f"{path}.{key}", ancestors=next_ancestors
            )
        return canonical

    raise TypeError(f"{path} has unsupported type {type(value).__name__}")


def strategy_identity_digest(
    symbol: str,
    horizon: str,
    strategy_family: str,
    rule_parameters: dict[str, Any],
) -> str:
    """Build a stable SHA-256 identity for one exact backtested strategy.

    Inputs are deliberately validated rather than coerced. Symbols must be
    canonical USDT market identifiers, horizons and families must be known,
    and rule parameters must be non-empty JSON-compatible deterministic data.
    This digest is an identity only; generating one conveys no approval.
    """
    if type(symbol) is not str or not symbol or not _SYMBOL_RE.fullmatch(symbol):
        raise ValueError("symbol must be a canonical supported USDT market identifier")
    if type(horizon) is not str or horizon not in _SUPPORTED_HORIZONS:
        raise ValueError("horizon is missing or unsupported")
    if type(strategy_family) is not str or strategy_family not in STRATEGY_FAMILIES:
        raise ValueError("strategy_family is missing or unsupported")
    if type(rule_parameters) is not dict or not rule_parameters:
        raise ValueError("rule_parameters must be a non-empty dictionary")

    canonical_rules = _canonical_rule_value(
        rule_parameters, path="rule_parameters", ancestors=set()
    )
    identity = {
        "horizon": horizon,
        "rule_parameters": canonical_rules,
        "strategy_family": strategy_family,
        "symbol": symbol,
        "version": _IDENTITY_VERSION,
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

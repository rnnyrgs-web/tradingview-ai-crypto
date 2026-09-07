"""Canonical identities for exact, research-only strategy definitions.

This module deliberately contains no approval or promotion state.  An identity
only proves that the same explicit definition was named; it is not evidence
that the strategy is safe or eligible for live trading.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from strategy_families import STRATEGY_FAMILIES


IDENTITY_VERSION = 1
SUPPORTED_HORIZONS = frozenset({"15m", "1H", "4H", "1D"})

_SYMBOL_RE = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+(?:-SWAP)?$")
_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class StrategyIdentityError(ValueError):
    """Raised when an exact canonical strategy identity cannot be built."""


@dataclass(frozen=True)
class StrategyIdentity:
    """Immutable serialized definition and its SHA-256 fingerprint."""

    canonical_definition: str
    fingerprint: str


def _validate_value(value: Any, path: str) -> Any:
    """Validate and copy values into the deliberately small identity format."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0):
            raise StrategyIdentityError(f"{path} contains a non-canonical number")
        return value
    if isinstance(value, str):
        if not value or value != value.strip():
            raise StrategyIdentityError(f"{path} contains an empty or non-canonical string")
        if any(ord(character) < 32 or ord(character) > 126 for character in value):
            raise StrategyIdentityError(f"{path} contains unsupported characters")
        return value
    if isinstance(value, list):
        if not value:
            raise StrategyIdentityError(f"{path} must not contain an empty list")
        return [_validate_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        return _validate_mapping(value, path)
    raise StrategyIdentityError(f"{path} contains unsupported value type {type(value).__name__}")


def _validate_mapping(value: Mapping[str, Any], path: str) -> dict[str, Any]:
    if not value:
        raise StrategyIdentityError(f"{path} must be a non-empty mapping")

    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not _FIELD_RE.fullmatch(key):
            raise StrategyIdentityError(f"{path} contains a malformed or non-canonical field name")
        result[key] = _validate_value(item, f"{path}.{key}")
    return result


def canonical_strategy_definition(
    symbol: str,
    horizon: str,
    strategy_family: str,
    rule_parameters: Mapping[str, Any],
    execution_assumptions: Mapping[str, Any],
) -> str:
    """Return the canonical JSON definition, rejecting ambiguity fail closed.

    Symbols, horizons, family names, and field names must already be canonical;
    this function never silently strips whitespace or changes case.
    """
    if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
        raise StrategyIdentityError("symbol is missing, malformed, or non-canonical")
    if not isinstance(horizon, str) or horizon not in SUPPORTED_HORIZONS:
        raise StrategyIdentityError("horizon is missing, non-canonical, or unsupported")
    if not isinstance(strategy_family, str) or strategy_family not in STRATEGY_FAMILIES:
        raise StrategyIdentityError("strategy_family is missing, non-canonical, or unsupported")
    if not isinstance(rule_parameters, Mapping):
        raise StrategyIdentityError("rule_parameters must be an explicit non-empty mapping")
    if not isinstance(execution_assumptions, Mapping):
        raise StrategyIdentityError("execution_assumptions must be an explicit non-empty mapping")

    definition = {
        "execution_assumptions": _validate_mapping(execution_assumptions, "execution_assumptions"),
        "horizon": horizon,
        "identity_version": IDENTITY_VERSION,
        "rule_parameters": _validate_mapping(rule_parameters, "rule_parameters"),
        "strategy_family": strategy_family,
        "symbol": symbol,
    }
    return json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_strategy_identity(
    symbol: str,
    horizon: str,
    strategy_family: str,
    rule_parameters: Mapping[str, Any],
    execution_assumptions: Mapping[str, Any],
) -> StrategyIdentity:
    """Build a deterministic identity without granting any approval status."""
    canonical = canonical_strategy_definition(
        symbol,
        horizon,
        strategy_family,
        rule_parameters,
        execution_assumptions,
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return StrategyIdentity(canonical_definition=canonical, fingerprint=fingerprint)


def strategy_fingerprint(
    symbol: str,
    horizon: str,
    strategy_family: str,
    rule_parameters: Mapping[str, Any],
    execution_assumptions: Mapping[str, Any],
) -> str:
    """Convenience API returning only the canonical SHA-256 fingerprint."""
    return build_strategy_identity(
        symbol,
        horizon,
        strategy_family,
        rule_parameters,
        execution_assumptions,
    ).fingerprint

"""Fail-closed bridge between research evidence and live BUY/SELL signals.

A production signal may be marked TRADE only when its exact strategy key has
been explicitly promoted here after repeated research validation. A single OOS
pass is not sufficient. Unknown or missing strategy evidence always remains
WAIT / RESEARCH_ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_identity import build_strategy_identity
from promotion_manifest import find_verified_promotion


@dataclass(frozen=True)
class LiveValidationDecision:
    approved: bool
    status: str
    reason: str
    identity: dict


def normalize_strategy_key(symbol: str, horizon: str, strategy_family: str) -> tuple[str, str, str]:
    return (
        str(symbol or "").strip().upper(),
        str(horizon or "").strip(),
        str(strategy_family or "").strip().lower(),
    )


def validate_live_strategy(symbol: str, horizon: str, strategy_family: str) -> LiveValidationDecision:
    key = normalize_strategy_key(symbol, horizon, strategy_family)
    identity = build_strategy_identity(*key)
    if not all(key):
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason="Missing exact research-validated strategy identity.",
            identity=identity,
        )
    if not identity["timeframes"]:
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason="Unknown production horizon in strategy identity.",
            identity=identity,
        )
    approved, reason = find_verified_promotion(identity)
    if not approved:
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason=reason,
            identity=identity,
        )
    return LiveValidationDecision(
        approved=True,
        status="LIVE_VALIDATED",
        reason=reason,
        identity=identity,
    )

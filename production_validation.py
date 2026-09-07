"""Fail-closed bridge between research evidence and live BUY/SELL signals.

A production signal may be marked TRADE only when its exact strategy key has
been explicitly promoted here after repeated research validation. A single OOS
pass is not sufficient. Unknown or missing strategy evidence always remains
WAIT / RESEARCH_ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass


# Intentionally empty until a strategy has passed the full promotion process:
# repeated backtests, validation, untouched OOS holdout, robustness/stability
# review, strategy-registry approval, and production-risk approval.
#
# Entries must use exact deterministic keys: (SYMBOL, PRODUCTION_HORIZON, FAMILY).
# Do not populate this set from AI output or from a single research artifact.
LIVE_VALIDATED_STRATEGIES: frozenset[tuple[str, str, str]] = frozenset()


@dataclass(frozen=True)
class LiveValidationDecision:
    approved: bool
    status: str
    reason: str


def normalize_strategy_key(symbol: str, horizon: str, strategy_family: str) -> tuple[str, str, str]:
    return (
        str(symbol or "").strip().upper(),
        str(horizon or "").strip(),
        str(strategy_family or "").strip().lower(),
    )


def validate_live_strategy(symbol: str, horizon: str, strategy_family: str) -> LiveValidationDecision:
    key = normalize_strategy_key(symbol, horizon, strategy_family)
    if not all(key):
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason="Missing exact research-validated strategy identity.",
        )
    if key not in LIVE_VALIDATED_STRATEGIES:
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason="Strategy has not completed the full live-promotion validation process.",
        )
    return LiveValidationDecision(
        approved=True,
        status="LIVE_VALIDATED",
        reason="Exact strategy key is explicitly approved for live production use.",
    )

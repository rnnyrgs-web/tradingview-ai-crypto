"""Fail-closed bridge between research evidence and live BUY/SELL signals.

A production signal may be marked TRADE only when its exact strategy key has
both an independently verified promotion and enough genuine forward evidence.
Historical/OOS evidence alone is never sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass

from forward_proof import assess_forward_proof
from promotion_manifest import find_verified_promotion
from strategy_identity import build_strategy_identity


@dataclass(frozen=True)
class LiveValidationDecision:
    approved: bool
    status: str
    reason: str
    identity: dict
    forward_proof: dict | None = None


def normalize_strategy_key(symbol: str, horizon: str, strategy_family: str) -> tuple[str, str, str]:
    return (
        str(symbol or "").strip().upper(),
        str(horizon or "").strip(),
        str(strategy_family or "").strip().lower(),
    )


def validate_live_strategy(symbol: str, horizon: str, strategy_family: str, resolved_predictions=None) -> LiveValidationDecision:
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

    promoted, promotion_reason = find_verified_promotion(identity)
    if not promoted:
        return LiveValidationDecision(
            approved=False,
            status="RESEARCH_ONLY",
            reason=promotion_reason,
            identity=identity,
        )

    forward_proof = assess_forward_proof(identity, key[1], resolved_predictions or [])
    if not forward_proof.get("passed"):
        return LiveValidationDecision(
            approved=False,
            status="FORWARD_PROOF_REQUIRED",
            reason=f"Signed promotion verified, but genuine forward proof is blocked: {forward_proof.get('reason', 'unknown')}.",
            identity=identity,
            forward_proof=forward_proof,
        )

    return LiveValidationDecision(
        approved=True,
        status="LIVE_VALIDATED",
        reason=f"{promotion_reason} Genuine independent forward proof also passed.",
        identity=identity,
        forward_proof=forward_proof,
    )

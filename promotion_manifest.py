"""Two-party, fail-closed verification for live strategy promotions."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

from research_artifact import canonical_json


ROOT = Path(__file__).resolve().parent
PROMOTIONS_PATH = ROOT / "live_promotions.json"
REQUIRED_STAGES = (
    "repeated_backtests",
    "validation",
    "untouched_oos",
    "robustness_stability",
    "strategy_registry",
    "production_risk",
)
APPROVAL_KEYS = {
    "strategy_registry": "STRATEGY_REGISTRY_SIGNING_KEY",
    "production_risk": "PRODUCTION_RISK_SIGNING_KEY",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def promotion_core(promotion: dict) -> dict:
    return {
        "schema_version": promotion.get("schema_version"),
        "status": promotion.get("status"),
        "identity": promotion.get("identity"),
        "evidence_sha256": promotion.get("evidence_sha256"),
        "stages": promotion.get("stages"),
    }


def approval_signature(promotion: dict, role: str, key: str) -> str:
    message = canonical_json({"role": role, "promotion": promotion_core(promotion)})
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_promotion(promotion: dict, expected_identity: dict) -> tuple[bool, str]:
    try:
        if not isinstance(promotion, dict) or not isinstance(expected_identity, dict):
            return False, "Promotion manifest is malformed."
        if promotion.get("schema_version") != 1 or promotion.get("status") != "APPROVED":
            return False, "Promotion schema or status is not approved."
        if promotion.get("identity") != expected_identity:
            return False, "Promotion identity does not match current research code."
        evidence = promotion.get("evidence_sha256")
        if not isinstance(evidence, list) or len(set(evidence)) < 3:
            return False, "At least three distinct research artifacts are required."
        if any(not isinstance(item, str) or not SHA256_RE.fullmatch(item) for item in evidence):
            return False, "Research evidence contains an invalid SHA-256 digest."
        stages = promotion.get("stages")
        if not isinstance(stages, dict) or any(stages.get(stage) is not True for stage in REQUIRED_STAGES):
            return False, "The full research-to-production validation chain is incomplete."
        approvals = promotion.get("approvals")
        if not isinstance(approvals, dict):
            return False, "Independent approvals are missing."
        for role, env_name in APPROVAL_KEYS.items():
            key = os.getenv(env_name, "")
            approval = approvals.get(role)
            if len(key) < 32 or not isinstance(approval, dict):
                return False, f"{role} approval key or attestation is missing."
            supplied = str(approval.get("signature", ""))
            expected = approval_signature(promotion, role, key)
            if not hmac.compare_digest(supplied, expected):
                return False, f"{role} approval signature is invalid."
    except (TypeError, ValueError):
        return False, "Promotion manifest is malformed."
    return True, "Immutable evidence chain and both independent approvals verified."


def load_promotions(path: Path = PROMOTIONS_PATH) -> list[dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if document.get("schema_version") != 1 or not isinstance(document.get("promotions"), list):
        return []
    return document["promotions"]


def find_verified_promotion(identity: dict, path: Path = PROMOTIONS_PATH) -> tuple[bool, str]:
    for promotion in load_promotions(path):
        if not isinstance(promotion, dict):
            continue
        promotion_identity = promotion.get("identity")
        if not isinstance(promotion_identity, dict):
            continue
        if promotion_identity.get("fingerprint") != identity.get("fingerprint"):
            continue
        approved, reason = verify_promotion(promotion, identity)
        if approved:
            return True, reason
        return False, reason
    return False, "No promotion manifest exists for the exact strategy fingerprint."

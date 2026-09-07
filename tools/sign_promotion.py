"""Apply exactly one role's HMAC attestation to an existing promotion."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from promotion_manifest import APPROVAL_KEYS, approval_signature


def sign_document(document: dict, fingerprint: str, role: str, key: str) -> dict:
    if role not in APPROVAL_KEYS:
        raise ValueError("unknown approval role")
    if len(key) < 32:
        raise ValueError("signing key must contain at least 32 characters")
    promotions = document.get("promotions")
    if document.get("schema_version") != 1 or not isinstance(promotions, list):
        raise ValueError("invalid promotion document")
    matches = [item for item in promotions if isinstance(item, dict) and (item.get("identity") or {}).get("fingerprint") == fingerprint]
    if len(matches) != 1:
        raise ValueError("fingerprint must match exactly one promotion")
    promotion = matches[0]
    promotion.setdefault("approvals", {})[role] = {
        "signature": approval_signature(promotion, role, key),
    }
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="live_promotions.json")
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--role", choices=tuple(APPROVAL_KEYS), required=True)
    args = parser.parse_args()
    env_name = APPROVAL_KEYS[args.role]
    key = os.getenv(env_name, "")
    path = Path(args.manifest)
    document = json.loads(path.read_text(encoding="utf-8"))
    signed = sign_document(document, args.fingerprint, args.role, key)
    path.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    print(f"Applied {args.role} attestation to {args.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

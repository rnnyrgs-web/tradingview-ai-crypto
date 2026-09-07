"""Fail a production workflow when a scan hides errors or unsafe trades."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def validate_scan_payload(payload: dict) -> list[str]:
    errors = []
    if payload.get("ok") is not True:
        errors.append("scan did not report ok=true")
    if int(payload.get("universe_count") or 0) <= 0:
        errors.append("empty market universe")
    if int(payload.get("deep_scanned") or 0) <= 0:
        errors.append("no markets completed deep scan")
    attempted = int(payload.get("deep_scanned") or 0) + int(payload.get("scan_error_count") or 0)
    if attempted and int(payload.get("scan_error_count") or 0) / attempted > 0.20:
        errors.append("more than 20% of deep-scan candidates failed")
    if payload.get("ai_error"):
        errors.append("AI review failed")
    if payload.get("opportunity_error"):
        errors.append("opportunity persistence failed")

    for signal in payload.get("signals") or []:
        validation = (signal.get("raw_analysis") or {}).get("research_validation") or {}
        if str(signal.get("action", "")).upper() == "TRADE" and validation.get("approved") is not True:
            errors.append(f"unvalidated TRADE escaped gate: {signal.get('symbol', 'UNKNOWN')}")
        identity = validation.get("strategy_identity") or {}
        if not identity.get("fingerprint"):
            errors.append(f"missing strategy fingerprint: {signal.get('symbol', 'UNKNOWN')}")
    return errors


def main(path: str) -> int:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid scan response: {type(exc).__name__}", file=sys.stderr)
        return 1
    errors = validate_scan_payload(payload)
    if errors:
        print("Production scan validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "Production scan validation PASS: "
        f"universe={payload['universe_count']} deep={payload['deep_scanned']} "
        f"signals={payload.get('signals_saved', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

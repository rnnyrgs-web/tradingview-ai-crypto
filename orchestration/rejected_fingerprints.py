from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "orchestration" / "rejected_fingerprints.json"

REQUIRED_FIELDS = (
    "fingerprint_id",
    "fingerprint_version",
    "hypothesis",
    "economic_mechanism",
    "horizons_evaluated",
    "sample_sizes",
    "rejection_evidence",
    "rejection_reason",
    "rejection_date",
    "do_not_resubmit_same_fingerprint",
    "reconsideration_conditions",
)


def load_rejected_fingerprints(path: Path = DEFAULT_PATH) -> list[dict[str, Any]]:
    """Load the canonical rejected-fingerprint registry.

    Every entry must carry enough evidence that another engine can tell
    whether a proposed candidate is genuinely new or a rescue attempt of a
    fingerprint that already failed chronological falsification.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("rejected fingerprints registry must contain a list of entries")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("rejected fingerprint entry must be an object")
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise RuntimeError(f"rejected fingerprint entry missing fields: {missing}")
        fingerprint_id = str(entry["fingerprint_id"])
        if fingerprint_id in seen:
            raise RuntimeError(f"duplicate rejected fingerprint id: {fingerprint_id}")
        seen.add(fingerprint_id)
        if not isinstance(entry["horizons_evaluated"], list) or not entry["horizons_evaluated"]:
            raise RuntimeError(f"rejected fingerprint {fingerprint_id} must list evaluated horizons")
        if not isinstance(entry["do_not_resubmit_same_fingerprint"], bool):
            raise RuntimeError(f"rejected fingerprint {fingerprint_id} do_not_resubmit_same_fingerprint must be boolean")
    return entries


def is_rejected_fingerprint(fingerprint_id: str, entries: list[dict[str, Any]] | None = None) -> bool:
    """True only if ``fingerprint_id`` exactly matches a rejected, non-reconsiderable entry.

    This is an exact-id match, not a name/substring heuristic, so a
    genuinely different hypothesis is never barred merely because it shares
    a naming prefix with a rejected fingerprint.
    """
    active = entries if entries is not None else load_rejected_fingerprints()
    return any(
        entry["fingerprint_id"] == fingerprint_id and entry.get("do_not_resubmit_same_fingerprint")
        for entry in active
    )


def rejection_record(fingerprint_id: str, entries: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    active = entries if entries is not None else load_rejected_fingerprints()
    return next((entry for entry in active if entry["fingerprint_id"] == fingerprint_id), None)

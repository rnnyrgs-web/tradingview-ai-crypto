"""Outcome-blind derived history floors for Cohort-001 Stage-1 candidates.

These values are deterministic consequences of the already-frozen nested PIT feature
rules.  They do not alter candidate identities, thresholds, costs, or chronology.
`warmup_hours` is treated as a minimum history floor; a signal is ineligible until
all nested prior-only feature/reference observations required by the frozen contract
are fully formed.
"""
from __future__ import annotations

DERIVED_FIRST_ELIGIBLE_INDEX: dict[str, int] = {
    "DISC-RESIDUAL-REV-001-v1": 1056,
    "DISC-SIGNED-VOLUME-DRIFT-001-v1": 1443,
    "DISC-LOWVOL-DRIFT-REV-001-v1": 728,
    "DISC-MODERATEVOL-AUTOCORR-001-v1": 2184,
}

DECLARED_WARMUP_HOURS: dict[str, int] = {
    "DISC-RESIDUAL-REV-001-v1": 720,
    "DISC-SIGNED-VOLUME-DRIFT-001-v1": 720,
    "DISC-LOWVOL-DRIFT-REV-001-v1": 720,
    "DISC-MODERATEVOL-AUTOCORR-001-v1": 2160,
}


def first_eligible_index(candidate_id: str) -> int:
    """Return the exact structural first index implied by complete nested PIT windows."""
    try:
        return DERIVED_FIRST_ELIGIBLE_INDEX[candidate_id]
    except KeyError as exc:
        raise ValueError(f"candidate has no derived warmup override: {candidate_id}") from exc


def structurally_eligible(candidate_id: str, index: int) -> bool:
    """Return whether all frozen minimum/nested-history floors can be satisfied."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError("index must be a non-negative integer")
    floor = max(DECLARED_WARMUP_HOURS[candidate_id], first_eligible_index(candidate_id))
    return index >= floor

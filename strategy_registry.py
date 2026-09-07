"""Fail-closed longitudinal approval for researched strategies."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


RESEARCH_ONLY = "RESEARCH_ONLY"
LIVE_APPROVED = "LIVE_APPROVED"
MIN_SUCCESSFUL_OOS_RESULTS = 2


@dataclass(frozen=True)
class RegistryDecision:
    status: str
    live_approved: bool
    live_weight: float


def evaluate_repeated_oos_gate(
    oos_results: Iterable[Mapping[str, Any]] | None,
    *,
    requested_live_weight: float = 0.0,
) -> RegistryDecision:
    """Approve live use only after repeated, distinct, well-formed OOS passes.

    Each result must contain a non-empty ``window_id`` and a literal boolean
    ``passed`` value. Any malformed result fails the complete decision closed.
    """
    research_only = RegistryDecision(RESEARCH_ONLY, False, 0.0)
    if oos_results is None:
        return research_only

    try:
        results = list(oos_results)
    except TypeError:
        return research_only

    successful_windows = set()
    for result in results:
        if not isinstance(result, Mapping):
            return research_only
        window_id = result.get("window_id")
        passed = result.get("passed")
        if not isinstance(window_id, str) or not window_id.strip():
            return research_only
        if type(passed) is not bool:
            return research_only
        if passed:
            successful_windows.add(window_id.strip())

    if len(successful_windows) < MIN_SUCCESSFUL_OOS_RESULTS:
        return research_only
    if isinstance(requested_live_weight, bool) or not isinstance(
        requested_live_weight, (int, float)
    ):
        return research_only
    if requested_live_weight <= 0.0:
        return research_only

    return RegistryDecision(LIVE_APPROVED, True, float(requested_live_weight))

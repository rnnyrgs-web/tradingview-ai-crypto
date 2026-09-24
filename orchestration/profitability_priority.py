"""Documented, tested wrapper around the existing profitability-first priority scoring.

This module does NOT change ``research_director.mission_priority()`` or
``orchestration/specialist_coordination.py``'s ``next_task()``/``role_queue()``
ranking. Per the Lead Integrator's 2026-09-13 amendment to the multi-engine
coordination architecture, this module preserves current scoring behavior
exactly (see ``tests/test_profitability_priority.py::test_score_matches_mission_priority_exactly``)
and instead makes that scoring:

- explicitly documented (this docstring plus ``score_breakdown()`` below),
- machine-auditable (``score_breakdown()`` exposes every intermediate term
  a caller would otherwise have to re-derive from
  ``research_director.mission_priority()``'s source),
- covered by tests that pin its current documented properties so a future
  change is caught if it silently breaks one of them.

WHAT THE CURRENT FORMULA (``research_director.mission_priority``, unchanged) DOES::

    evidence_value   = 0.45 * info + 0.35 * falsify + 0.20 * samples
    economic_value   = 0.90 * profitability + 0.10 * actionable
    cost_efficiency  = 1 / (0.25 + 0.75 * compute_cost)
    score            = evidence_value * economic_value
                        * (0.35 + 0.65 * actionable) * cost_efficiency
    score           += 0.025 * signal_impact          # secondary tie-breaker
    score           += 0.04  * novelty                # secondary tie-breaker
    score           *= (1 - 0.75 * redundancy_risk)   # duplication penalty
    score           *= 0.08 or 0.02 if blocked        # heavy blocked discount

- Primary term: ``expected_profitability_impact`` dominates ``economic_value``
  (weight 0.90), which itself multiplies the whole score -- this is the
  "expected incremental after-cost economic value first" requirement.
- Secondary term: ``expected_signal_impact`` (genuine forward signal
  quality) enters only as a +0.025 additive tie-breaker, never as a
  multiplicative factor -- this is the "signal quality second" ordering.
- Compute/cost burden: ``compute_cost`` divides the score via
  ``cost_efficiency``.
- Duplication: ``redundancy_risk`` directly discounts the score up to 75%.
- Blocked work: discounted to 2-8% of its unblocked score.
- WAIT/no-task capability: this lives in ``orchestration.specialist_coordination.next_task``
  (wrapped below as ``select_next``), which returns ``None`` -- not a
  fabricated task -- when nothing READY/QUEUED exists for a role.

WHAT THE CURRENT FORMULA DOES **NOT** YET DO (documented gaps, not fixed by this module):

- No dedicated term for *contamination risk* -- a candidate that would reuse
  or bias an evidence window another task is still accumulating (for
  example DATA-BREADTH-001/COORD-DATA-007). ``blocker`` is a blunt override
  for that one specific case today, not a graded contamination-risk term.
- No dedicated term for *multiple-testing burden* -- how many other
  candidates are concurrently being searched, which should reduce a single
  candidate's priority per this repository's own
  ``multiple_testing.py`` ``log2(trial_count)`` scaling used elsewhere. The
  two systems are not currently connected.
- No dedicated term for *overfitting risk* distinct from
  ``redundancy_risk``/``novelty``.
- The weights themselves (0.45/0.35/0.20, 0.90/0.10, 0.25/0.75, 0.35/0.65,
  0.025, 0.04, 0.75, 0.08/0.02) are hand-tuned constants with no cited
  derivation, sensitivity analysis, or validation against realized
  outcomes anywhere in this codebase.

Per the Lead Integrator's explicit 2026-09-13 amendment, this module does
not retune or replace those weights -- doing so using untouched OOS/forward
outcomes would itself be exactly the kind of post-hoc threshold mining this
project's scientific discipline forbids elsewhere. Coordination task
``COORD-VAL-003`` (added by this same change,
``orchestration/specialist_coordination_overrides.json``) exists to close
the four gaps above and validate or replace the weights with a methodology
that itself avoids that trap. Until ``COORD-VAL-003`` resolves, treat
``mission_priority()``'s ranking as a directionally-reasonable, but not yet
scientifically validated, priority order -- not settled ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from research_director import mission_priority
from orchestration.specialist_coordination import next_task as _coordination_next_task


@dataclass(frozen=True)
class ScoreBreakdown:
    evidence_value: float
    economic_value: float
    cost_efficiency: float
    actionable_multiplier: float
    signal_tiebreak: float
    novelty_tiebreak: float
    redundancy_multiplier: float
    blocked_multiplier: float
    score: float


def _clamp01(value: float) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("mission estimate must be a finite number") from exc
    if not math.isfinite(normalized):
        raise ValueError("mission estimate must be a finite number")
    return max(0.0, min(1.0, normalized))


def score_breakdown(
    *,
    expected_information_gain: float,
    expected_signal_impact: float,
    sample_readiness: float,
    novelty: float,
    expected_profitability_impact: float | None = None,
    falsification_value: float = 0.5,
    actionable_evidence_probability: float = 0.5,
    compute_cost: float = 0.5,
    redundancy_risk: float = 0.0,
    blocker: str | None = None,
) -> ScoreBreakdown:
    """Decompose ``research_director.mission_priority()`` into its named terms.

    Returns the same final score ``mission_priority()`` would (pinned by
    ``test_score_matches_mission_priority_exactly``) plus every intermediate
    term, so a reviewer or another engine can audit *why* one candidate
    outranked another instead of only seeing the final number.
    """
    info = _clamp01(expected_information_gain)
    signal = _clamp01(expected_signal_impact)
    profitability = _clamp01(
        expected_signal_impact if expected_profitability_impact is None else expected_profitability_impact
    )
    samples = _clamp01(sample_readiness)
    novel = _clamp01(novelty)
    falsify = _clamp01(falsification_value)
    actionable = _clamp01(actionable_evidence_probability)
    cost = _clamp01(compute_cost)
    redundant = _clamp01(redundancy_risk)

    evidence_value = 0.45 * info + 0.35 * falsify + 0.20 * samples
    economic_value = 0.90 * profitability + 0.10 * actionable
    cost_efficiency = 1.0 / (0.25 + 0.75 * cost)
    actionable_multiplier = 0.35 + 0.65 * actionable
    redundancy_multiplier = 1.0 - 0.75 * redundant
    blocked_multiplier = 1.0 if not blocker else (0.08 if blocker == "InsufficientHistory" else 0.02)

    score = mission_priority(
        expected_information_gain=expected_information_gain,
        expected_signal_impact=expected_signal_impact,
        expected_profitability_impact=expected_profitability_impact,
        sample_readiness=sample_readiness,
        novelty=novelty,
        falsification_value=falsification_value,
        actionable_evidence_probability=actionable_evidence_probability,
        compute_cost=compute_cost,
        redundancy_risk=redundancy_risk,
        blocker=blocker,
    )

    return ScoreBreakdown(
        evidence_value=round(evidence_value, 6),
        economic_value=round(economic_value, 6),
        cost_efficiency=round(cost_efficiency, 6),
        actionable_multiplier=round(actionable_multiplier, 6),
        signal_tiebreak=round(0.025 * signal, 6),
        novelty_tiebreak=round(0.04 * novel, 6),
        redundancy_multiplier=round(redundancy_multiplier, 6),
        blocked_multiplier=blocked_multiplier,
        score=score,
    )


def select_next(coordination_state: dict[str, Any], role: str) -> dict[str, Any] | None:
    """WAIT-capable selection of a role's next task.

    Thin, documented pass-through to
    ``orchestration.specialist_coordination.next_task()``: returns ``None``
    when no clean READY/IN_PROGRESS/PR_OPEN/QUEUED task exists for ``role``,
    which is the correct WAIT/no-task outcome, not an error. Kept as a
    distinct named entry point so every engine's plan step calls one
    documented function instead of each independently re-implementing "what
    should I work on".
    """
    return _coordination_next_task(coordination_state, role)

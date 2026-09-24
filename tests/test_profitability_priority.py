import itertools

import pytest

from orchestration.profitability_priority import score_breakdown, select_next
from orchestration.specialist_coordination import load_state
from research_director import mission_priority


BASE_KWARGS = dict(
    expected_information_gain=0.6,
    expected_signal_impact=0.5,
    sample_readiness=0.7,
    novelty=0.3,
    expected_profitability_impact=0.8,
    falsification_value=0.4,
    actionable_evidence_probability=0.6,
    compute_cost=0.5,
    redundancy_risk=0.1,
    blocker=None,
)


def test_score_matches_mission_priority_exactly():
    """Pins that this PR changed no scoring behavior, per the explicit
    Lead Integrator instruction to preserve current behavior in this PR."""
    breakdown = score_breakdown(**BASE_KWARGS)
    direct = mission_priority(**BASE_KWARGS)
    assert breakdown.score == direct


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_audit_breakdown_rejects_nonfinite_scientific_estimates(nonfinite):
    with pytest.raises(ValueError, match="finite"):
        score_breakdown(**{**BASE_KWARGS, "expected_profitability_impact": nonfinite})


@pytest.mark.parametrize(
    "info,signal,samples,novelty,profitability,falsify,actionable,cost,redundancy,blocker",
    list(
        itertools.product(
            [0.0, 0.3, 0.9],
            [0.5],
            [0.5],
            [0.2],
            [0.1, 0.9],
            [0.5],
            [0.5],
            [0.5],
            [0.0],
            [None],
        )
    ),
)
def test_score_matches_mission_priority_across_a_grid(
    info, signal, samples, novelty, profitability, falsify, actionable, cost, redundancy, blocker
):
    kwargs = dict(
        expected_information_gain=info,
        expected_signal_impact=signal,
        sample_readiness=samples,
        novelty=novelty,
        expected_profitability_impact=profitability,
        falsification_value=falsify,
        actionable_evidence_probability=actionable,
        compute_cost=cost,
        redundancy_risk=redundancy,
        blocker=blocker,
    )
    assert score_breakdown(**kwargs).score == mission_priority(**kwargs)


def test_primary_term_is_expected_profitability_impact():
    """Documented property: profitability dominates economic_value (weight
    0.90), which itself multiplies the whole score -- raising profitability
    with everything else held fixed must strictly increase the score."""
    low = score_breakdown(**{**BASE_KWARGS, "expected_profitability_impact": 0.1})
    high = score_breakdown(**{**BASE_KWARGS, "expected_profitability_impact": 0.9})
    assert high.score > low.score
    assert high.economic_value > low.economic_value


def test_signal_quality_is_a_secondary_additive_tiebreak_only():
    """Documented property: expected_signal_impact enters only as a
    +0.025*signal additive term (applied before the redundancy-risk
    multiplier, which BASE_KWARGS sets to 0.1 -- isolated here via
    redundancy_risk=0.0 for a clean, direct delta), never multiplicatively,
    so its effect on the score is small and strictly bounded even at the
    extremes."""
    kwargs = {**BASE_KWARGS, "redundancy_risk": 0.0}
    low = score_breakdown(**{**kwargs, "expected_signal_impact": 0.0})
    high = score_breakdown(**{**kwargs, "expected_signal_impact": 1.0})
    assert high.score - low.score == pytest.approx(0.025, abs=1e-6)
    assert low.signal_tiebreak == 0.0
    assert high.signal_tiebreak == pytest.approx(0.025)


def test_compute_cost_burden_penalizes_score():
    cheap = score_breakdown(**{**BASE_KWARGS, "compute_cost": 0.0})
    expensive = score_breakdown(**{**BASE_KWARGS, "compute_cost": 1.0})
    assert cheap.score > expensive.score
    assert cheap.cost_efficiency > expensive.cost_efficiency


def test_duplication_redundancy_penalizes_score():
    unique = score_breakdown(**{**BASE_KWARGS, "redundancy_risk": 0.0})
    duplicate = score_breakdown(**{**BASE_KWARGS, "redundancy_risk": 1.0})
    assert unique.score > duplicate.score
    assert duplicate.redundancy_multiplier == pytest.approx(0.25)


def test_blocked_work_is_heavily_discounted():
    unblocked = score_breakdown(**{**BASE_KWARGS, "blocker": None})
    insufficient_history = score_breakdown(**{**BASE_KWARGS, "blocker": "InsufficientHistory"})
    other_blocker = score_breakdown(**{**BASE_KWARGS, "blocker": "SomeOtherReason"})
    assert insufficient_history.score < unblocked.score * 0.10
    assert other_blocker.score < unblocked.score * 0.05
    assert insufficient_history.blocked_multiplier == pytest.approx(0.08)
    assert other_blocker.blocked_multiplier == pytest.approx(0.02)


def test_select_next_returns_none_for_a_role_with_no_active_or_queued_task():
    """WAIT/no-task capability remains valid for roles intentionally parked
    until a strategy candidate earns deep validation."""
    state = load_state()
    assert select_next(state, "regime-selection") is None



def test_select_next_routes_phase_three_only_to_its_owner():
    from orchestration.specialist_coordination import next_task

    state = load_state()
    task = select_next(state, "data-market")
    assert task is None
    assert task == next_task(state, "data-market")
    assert select_next(state, "quant-research") is None
    review = select_next(state, "testing-security")
    assert review == next_task(state, "testing-security")
    assert review["id"] == "COORD-ARCH-ADVERSARIAL-001"
    assert review["issue"] == 462

def test_select_next_returns_the_same_task_as_next_task_for_an_active_role():
    from orchestration.specialist_coordination import next_task

    state = load_state()
    assert select_next(state, "signal-accuracy") == next_task(state, "signal-accuracy")
    assert select_next(state, "signal-accuracy") is not None

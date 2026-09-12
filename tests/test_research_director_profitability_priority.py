from research_director import build_mission, mission_priority, rank_missions


def test_explicit_profitability_impact_beats_headline_signal_impact():
    profitable = mission_priority(
        expected_information_gain=0.8,
        expected_signal_impact=0.55,
        expected_profitability_impact=0.90,
        sample_readiness=0.8,
        novelty=0.6,
        falsification_value=0.9,
        actionable_evidence_probability=0.8,
        compute_cost=0.4,
    )
    accurate_but_economically_weak = mission_priority(
        expected_information_gain=0.8,
        expected_signal_impact=0.99,
        expected_profitability_impact=0.20,
        sample_readiness=0.8,
        novelty=0.6,
        falsification_value=0.9,
        actionable_evidence_probability=0.8,
        compute_cost=0.4,
    )
    assert profitable > accurate_but_economically_weak


def test_ranked_mission_serializes_profitability_separately_from_signal_quality():
    money_first = build_mission(
        lane="execution",
        horizon="24h",
        direction="BUY_SELL_WAIT",
        theme="after_cost_edge",
        hypothesis="reduce adverse-selection losses",
        expected_information_gain=0.8,
        expected_signal_impact=0.60,
        expected_profitability_impact=0.90,
        sample_readiness=0.8,
        novelty=0.7,
        falsification_value=0.9,
        actionable_evidence_probability=0.8,
        compute_cost=0.4,
    )
    accuracy_first = build_mission(
        lane="accuracy",
        horizon="24h",
        direction="BUY_SELL_WAIT",
        theme="headline_precision",
        hypothesis="raise hit rate without economic evidence",
        expected_information_gain=0.8,
        expected_signal_impact=0.99,
        expected_profitability_impact=0.20,
        sample_readiness=0.8,
        novelty=0.7,
        falsification_value=0.9,
        actionable_evidence_probability=0.8,
        compute_cost=0.4,
    )
    ranked = rank_missions([accuracy_first, money_first])
    assert ranked[0].mission_id == money_first.mission_id
    payload = money_first.to_dict()
    assert payload["expected_profitability_impact"] == 0.90
    assert payload["expected_signal_impact"] == 0.60


def test_legacy_callers_fall_back_without_changing_existing_semantics():
    mission = build_mission(
        lane="legacy",
        horizon="24h",
        direction="BUY_SELL_WAIT",
        theme="compatibility",
        hypothesis="legacy callers remain valid",
        expected_information_gain=0.7,
        expected_signal_impact=0.65,
        sample_readiness=0.7,
        novelty=0.6,
    )
    assert mission.expected_profitability_impact == mission.expected_signal_impact == 0.65

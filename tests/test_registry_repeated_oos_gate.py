from strategy_registry import RESEARCH_ONLY, evaluate_repeated_oos_gate


def test_one_successful_oos_result_cannot_be_live_approved_or_weighted():
    decision = evaluate_repeated_oos_gate(
        [{"window_id": "2026-01", "passed": True}],
        requested_live_weight=0.25,
    )

    assert decision.status == RESEARCH_ONLY
    assert decision.live_approved is False
    assert decision.live_weight == 0.0

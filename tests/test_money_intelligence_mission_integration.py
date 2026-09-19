from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EpistemicClaim,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
)
from money_intelligence_mission_integration import (
    apply_causal_feedback,
    build_supported_missions,
    causal_feedback,
)


def _obs(ident, value, observed, available, *, metric="matched_return"):
    return PointInTimeObservation(
        observation_id=ident,
        metric_name=metric,
        value=value,
        unit="pct",
        observed_at=observed,
        available_at=available,
        retrieved_at=available,
        source_id="fixture-source",
        subject_id="SOL",
        currency="USD",
        measurement_window_hours=24,
        venue="aggregate",
        max_age_hours=24 * 3650,
        provenance_uri=f"fixture://{ident}",
    )


def _supported_memory(*, lanes=("big_move", "strategy_component")):
    memory = CausalRepricingMemory(half_life_days=30)
    formation = _obs(
        "formation-flow",
        10.0,
        "2026-09-01T00:00:00Z",
        "2026-09-01T01:00:00Z",
        metric="flow_intensity",
    )
    memory.register_observation(formation)
    hypothesis = FrozenHypothesis(
        hypothesis_id="h-flow-impact",
        statement="large verified flow intensity precedes relative repricing",
        mechanism_chain=("realized_flow", "usable_liquidity_impact", "repricing"),
        direction="positive",
        horizon_hours=24,
        falsifier="matched outcomes do not exceed frozen controls",
        matched_controls=("matched-control-v1",),
        lanes=lanes,
        created_at="2026-09-01T02:00:00Z",
        source_observation_ids=("formation-flow",),
        family_id="treasury-flow-family",
        evaluation_method="matched_mean_diff_v1",
        family_size=2,
        alpha=0.05,
    )
    memory.register_hypothesis(hypothesis)
    memory.register_observation(
        _obs("outcome-1", 2.0, "2026-09-02T00:00:00Z", "2026-09-02T01:00:00Z")
    )
    memory.register_observation(
        _obs("control-1", 0.0, "2026-09-02T00:00:00Z", "2026-09-02T01:00:00Z")
    )
    memory.record_evidence(
        EvidenceEvent(
            event_id="support-1",
            hypothesis_id="h-flow-impact",
            evaluated_at="2026-09-02T02:00:00Z",
            kind="support",
            matched_controls=("matched-control-v1",),
            outcome_observation_ids=("outcome-1",),
            control_observation_ids=("control-1",),
            evaluation_method="matched_mean_diff_v1",
            sample_size=20,
            confirmatory=True,
            p_value=0.01,
        )
    )
    return memory


def test_supported_structured_evidence_emits_fresh_lane_specific_research_missions():
    memory = _supported_memory()
    rows = build_supported_missions(memory, as_of="2026-09-02T03:00:00Z")
    assert {row["lane"] for row in rows} == {"big-move-causal", "strategy-component-causal"}
    assert len({row["experiment_id"] for row in rows}) == 2
    for row in rows:
        assert row["experiment_id"].startswith("mi-downstream-v1:")
        assert row["causal_repricing"]["evidence_level"] == "SUPPORTED_MECHANISM_RESEARCH_ONLY"
        assert row["causal_repricing"]["narrative_evidence_consumed"] is False
        assert row["causal_repricing"]["requires_fresh_chronological_validation"] is True
        assert row["causal_repricing"]["formation_or_confirmation_rows_reusable"] is False
        assert row["research_only"] is True
        assert row["trade_authority"] is False
        assert row["promotion_authority"] is False
        assert row["oos_opening_authority"] is False


def test_narrative_claim_cannot_change_mission_eligibility_or_fingerprint():
    memory = _supported_memory(lanes=("big_move",))
    before = build_supported_missions(memory, as_of="2026-09-02T03:00:00Z")
    memory.register_claim(
        EpistemicClaim(
            claim_id="narrative-1",
            level="inference",
            text="this narrative sounds extremely bullish and could 2x",
            created_at="2026-09-02T03:00:00Z",
            source_observation_ids=("formation-flow",),
        )
    )
    after = build_supported_missions(memory, as_of="2026-09-02T03:00:00Z")
    assert before == after


def test_later_contradiction_removes_causal_mission_from_autonomous_eligibility():
    memory = _supported_memory(lanes=("big_move",))
    memory.register_observation(
        _obs("outcome-2", -2.0, "2026-09-03T00:00:00Z", "2026-09-03T01:00:00Z")
    )
    memory.register_observation(
        _obs("control-2", 0.0, "2026-09-03T00:00:00Z", "2026-09-03T01:00:00Z")
    )
    memory.record_evidence(
        EvidenceEvent(
            event_id="contradiction-1",
            hypothesis_id="h-flow-impact",
            evaluated_at="2026-09-03T02:00:00Z",
            kind="contradiction",
            matched_controls=("matched-control-v1",),
            outcome_observation_ids=("outcome-2",),
            control_observation_ids=("control-2",),
            evaluation_method="matched_mean_diff_v1",
            sample_size=20,
            confirmatory=True,
        )
    )
    assert build_supported_missions(memory, as_of="2026-09-03T03:00:00Z") == []


def test_decay_and_rejection_each_fail_closed_for_downstream_emission():
    memory = _supported_memory(lanes=("strategy_component",))
    assert build_supported_missions(memory, as_of="2026-09-02T03:00:00Z")
    assert build_supported_missions(memory, as_of="2027-09-02T03:00:00Z") == []

    memory = _supported_memory(lanes=("strategy_component",))
    memory.reject_hypothesis("h-flow-impact")
    assert build_supported_missions(memory, as_of="2026-09-02T03:00:00Z") == []


def test_unavailable_or_corrupt_durable_memory_cannot_authorize_stale_causal_work():
    def broken_loader():
        raise CausalMemoryError("backend unavailable")

    feedback = causal_feedback(loader=broken_loader, as_of="2026-09-02T03:00:00Z")
    assert feedback["status"] == "WAIT_CAUSAL_MEMORY_UNAVAILABLE"
    assert feedback["missions"] == []
    assert feedback["structured_evidence_consumed"] is False
    assert feedback["trade_authority"] is False
    assert feedback["promotion_authority"] is False


def test_supported_causal_evidence_changes_actual_next_mission_ranking_surface():
    memory = _supported_memory(lanes=("big_move",))
    base = {
        "missions": [],
        "next_missions": [],
        "daily_lead_report": {"highest_priority_next_missions": []},
    }
    result = apply_causal_feedback(
        base,
        loader=lambda: memory,
        as_of="2026-09-02T03:00:00Z",
    )
    assert result["money_intelligence_causal"]["status"] == "AVAILABLE"
    assert result["next_missions"]
    assert result["next_missions"][0]["lane"] == "big-move-causal"
    assert result["daily_lead_report"]["highest_priority_next_missions"] == result["next_missions"]


def test_invalid_loader_type_fails_closed():
    feedback = causal_feedback(loader=lambda: object(), as_of="2026-09-02T03:00:00Z")
    assert feedback["status"] == "WAIT_CAUSAL_MEMORY_UNAVAILABLE"
    assert feedback["mission_count"] == 0

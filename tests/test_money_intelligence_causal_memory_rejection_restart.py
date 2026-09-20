import pytest

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
)


def _observation(source_id: str = "source-a") -> PointInTimeObservation:
    return PointInTimeObservation(
        observation_id="flow",
        metric_name="flow_24h",
        value=20.0,
        unit="usd",
        observed_at="2026-09-01T00:00:00Z",
        available_at="2026-09-01T01:00:00Z",
        retrieved_at="2026-09-01T02:00:00Z",
        source_id=source_id,
        subject_id="BTC-USD",
        currency="USD",
        measurement_window_hours=24,
        venue="coinbase",
        max_age_hours=72,
        revision_id="r1",
        provenance_uri="source://fixture",
    )


def _hypothesis(hypothesis_id: str = "H1") -> FrozenHypothesis:
    return FrozenHypothesis(
        hypothesis_id=hypothesis_id,
        statement="Large flow relative to float causes short-horizon upward repricing pressure.",
        mechanism_chain=("net_flow", "relative_scarcity", "repricing"),
        direction="positive",
        horizon_hours=72,
        falsifier="matched-control excess return <= 0 after costs",
        matched_controls=("market_beta", "volatility_regime"),
        lanes=("big_move", "strategy_component"),
        created_at="2026-09-02T00:00:00Z",
        source_observation_ids=("flow",),
        family_id="FLOW-SCARCITY-001",
        evaluation_method="matched_control_mean_difference_v1",
        family_size=2,
        alpha=0.05,
    )


def test_rejected_historical_hypothesis_survives_restart_and_stays_ineligible(tmp_path):
    memory = CausalRepricingMemory()
    memory.register_observation(_observation())
    hypothesis = _hypothesis()
    memory.register_hypothesis(hypothesis)
    for observation_id, metric_name, value in (
        ("outcome", "forward_return_72h", 0.08),
        ("control", "matched_control_return_72h", 0.01),
    ):
        memory.register_observation(
            PointInTimeObservation(
                observation_id=observation_id,
                metric_name=metric_name,
                value=value,
                unit="ratio",
                observed_at="2026-09-02T01:00:00Z",
                available_at="2026-09-02T04:00:00Z",
                retrieved_at="2026-09-02T05:00:00Z",
                source_id="test-source",
                subject_id="BTC-USD",
                currency="ratio",
                measurement_window_hours=72,
                venue="coinbase",
                max_age_hours=72,
            )
        )
    memory.record_evidence(
        EvidenceEvent(
            event_id="support-1",
            hypothesis_id="H1",
            evaluated_at="2026-09-03T00:00:00Z",
            kind="support",
            matched_controls=("market_beta", "volatility_regime"),
            outcome_observation_ids=("outcome",),
            control_observation_ids=("control",),
            evaluation_method="matched_control_mean_difference_v1",
            sample_size=1,
            confirmatory=False,
            p_value=None,
        )
    )
    design_fp, effective_fp = memory.reject_hypothesis("H1")
    assert design_fp in memory.rejected_fingerprints
    assert effective_fp in memory.rejected_fingerprints
    assert memory.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) is None

    path = tmp_path / "causal-memory.json"
    memory.save(path)
    restored = CausalRepricingMemory.load(path)

    assert restored.to_document() == memory.to_document()
    assert design_fp in restored.rejected_fingerprints
    assert effective_fp in restored.rejected_fingerprints
    assert restored.research_artifact(
        "H1", lane="strategy_component", as_of="2026-09-03T00:00:00Z"
    ) is None

    fresh_id_same_design = _hypothesis("H2")
    with pytest.raises(CausalMemoryError, match="rejected"):
        restored.register_hypothesis(fresh_id_same_design)


def test_effective_fingerprint_changes_when_point_in_time_provenance_changes():
    first = CausalRepricingMemory()
    first.register_observation(_observation("source-a"))
    hypothesis = _hypothesis()
    first.register_hypothesis(hypothesis)
    first_effective = first.effective_fingerprint(hypothesis)

    second = CausalRepricingMemory()
    second.register_observation(_observation("source-b"))
    second.register_hypothesis(hypothesis)
    second_effective = second.effective_fingerprint(hypothesis)

    assert first_effective != second_effective
    assert hypothesis.fingerprint == _hypothesis().fingerprint

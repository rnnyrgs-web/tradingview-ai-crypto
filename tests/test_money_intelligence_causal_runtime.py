import json

import pytest

import money_intelligence_causal_runtime as runtime
from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EpistemicClaim,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
)


class MemoryStore:
    def __init__(self, memory):
        self.memory = memory

    def load(self):
        if isinstance(self.memory, Exception):
            raise self.memory
        return CausalRepricingMemory.from_document(self.memory.to_document())


def _observation(
    observation_id,
    metric_name,
    value,
    *,
    observed_at,
    available_at,
    retrieved_at,
):
    return PointInTimeObservation(
        observation_id=observation_id,
        metric_name=metric_name,
        value=value,
        unit="ratio",
        observed_at=observed_at,
        available_at=available_at,
        retrieved_at=retrieved_at,
        source_id="sealed-test-source",
        subject_id="BTC-USD",
        currency="ratio",
        measurement_window_hours=72,
        venue="coinbase",
        max_age_hours=720,
        revision_id="r1",
        provenance_uri=f"source://{observation_id}",
    )


def qualified_memory(*, exploratory=False, contradiction=False, half_life_days=30.0):
    memory = CausalRepricingMemory(half_life_days=half_life_days)
    memory.register_observation(
        _observation(
            "formation",
            "flow_float",
            0.05,
            observed_at="2026-09-01T00:00:00Z",
            available_at="2026-09-01T01:00:00Z",
            retrieved_at="2026-09-01T02:00:00Z",
        )
    )
    memory.register_claim(
        EpistemicClaim(
            claim_id="narrative-only",
            level="inference",
            text="A plausible story is not mission evidence.",
            created_at="2026-09-01T03:00:00Z",
            source_observation_ids=("formation",),
        )
    )
    hypothesis = FrozenHypothesis(
        hypothesis_id="H-RUNTIME-1",
        statement="Flow relative to float creates short-horizon upward repricing pressure.",
        mechanism_chain=("net_flow", "relative_scarcity", "repricing"),
        direction="positive",
        horizon_hours=72,
        falsifier="matched-control excess return <= 0 after costs",
        matched_controls=("market_beta", "volatility_regime"),
        lanes=("big_move", "strategy_component"),
        created_at="2026-09-02T00:00:00Z",
        source_observation_ids=("formation",),
        family_id="RUNTIME-CAUSAL-001",
        evaluation_method="matched_control_mean_difference_v1",
        family_size=2,
        alpha=0.05,
    )
    memory.register_hypothesis(hypothesis)
    for observation_id, metric_name, value in (
        ("support-outcome", "forward_return_72h", 0.08),
        ("support-control", "matched_control_return_72h", 0.01),
    ):
        memory.register_observation(
            _observation(
                observation_id,
                metric_name,
                value,
                observed_at="2026-09-02T01:00:00Z",
                available_at="2026-09-02T04:00:00Z",
                retrieved_at="2026-09-02T05:00:00Z",
            )
        )
    memory.record_evidence(
        EvidenceEvent(
            event_id="support-1",
            hypothesis_id=hypothesis.hypothesis_id,
            evaluated_at="2026-09-03T00:00:00Z",
            kind="support",
            matched_controls=hypothesis.matched_controls,
            outcome_observation_ids=("support-outcome",),
            control_observation_ids=("support-control",),
            evaluation_method=hypothesis.evaluation_method,
            sample_size=40,
            confirmatory=not exploratory,
            p_value=0.01,
        )
    )
    if contradiction:
        for observation_id, metric_name, value in (
            ("contradiction-outcome", "forward_return_72h", -0.08),
            ("contradiction-control", "matched_control_return_72h", 0.01),
        ):
            memory.register_observation(
                _observation(
                    observation_id,
                    metric_name,
                    value,
                    observed_at="2026-09-04T01:00:00Z",
                    available_at="2026-09-04T04:00:00Z",
                    retrieved_at="2026-09-04T05:00:00Z",
                )
            )
        memory.record_evidence(
            EvidenceEvent(
                event_id="contradiction-1",
                hypothesis_id=hypothesis.hypothesis_id,
                evaluated_at="2026-09-05T00:00:00Z",
                kind="contradiction",
                matched_controls=hypothesis.matched_controls,
                outcome_observation_ids=("contradiction-outcome",),
                control_observation_ids=("contradiction-control",),
                evaluation_method=hypothesis.evaluation_method,
                sample_size=40,
                p_value=0.01,
            )
        )
    return memory


def test_confirmatory_support_yields_provenance_bound_research_only_missions(tmp_path, monkeypatch):
    registry = tmp_path / "rejected.json"
    registry.write_text('{"entries": []}', encoding="utf-8")
    monkeypatch.setattr(runtime, "REJECTED_REGISTRY_PATH", registry)
    memory = qualified_memory()

    result = runtime.causal_mission_feedback(
        as_of="2026-09-03T01:00:00Z", store=MemoryStore(memory)
    )

    assert result["status"] == "READY"
    assert result["content_digest"] == memory.to_document()["content_digest"]
    assert [mission["lane"] for mission in result["missions"]] == [
        "big-move",
        "strategy-component",
    ]
    assert len({mission["mission_id"] for mission in result["missions"]}) == 2
    for mission in result["missions"]:
        evidence = mission["causal_evidence"]
        assert evidence["hypothesis_id"] == "H-RUNTIME-1"
        assert evidence["memory_content_digest"] == result["content_digest"]
        assert evidence["effective_fingerprint"].startswith("mi-causal-pit-v1:")
        assert evidence["event_fingerprints"]
        assert mission["experiment_id"] == evidence["effective_fingerprint"]
        assert mission["trade_authority"] is False
        assert mission["promotion_authority"] is False
        assert mission["oos_opening_authority"] is False


@pytest.mark.parametrize(
    "memory,as_of",
    [
        (qualified_memory(exploratory=True), "2026-09-03T01:00:00Z"),
        (qualified_memory(contradiction=True), "2026-09-05T01:00:00Z"),
        (qualified_memory(half_life_days=1.0), "2026-10-03T01:00:00Z"),
    ],
)
def test_exploratory_contradicted_and_decayed_evidence_do_not_create_missions(
    memory, as_of, tmp_path, monkeypatch
):
    registry = tmp_path / "rejected.json"
    registry.write_text('{"entries": []}', encoding="utf-8")
    monkeypatch.setattr(runtime, "REJECTED_REGISTRY_PATH", registry)

    result = runtime.causal_mission_feedback(as_of=as_of, store=MemoryStore(memory))

    assert result["status"] == "READY"
    assert result["missions"] == []


@pytest.mark.parametrize("rejected_field", ["fingerprint_id", "design", "effective"])
def test_canonical_exact_rejection_vetoes_mission_after_restart(
    rejected_field, tmp_path, monkeypatch
):
    memory = qualified_memory()
    hypothesis = memory.hypotheses["H-RUNTIME-1"]
    values = {
        "fingerprint_id": hypothesis.hypothesis_id,
        "design": hypothesis.fingerprint,
        "effective": memory.effective_fingerprint(hypothesis),
    }
    registry = tmp_path / "rejected.json"
    registry.write_text(
        json.dumps({"entries": [{"fingerprint_id": values[rejected_field]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "REJECTED_REGISTRY_PATH", registry)

    result = runtime.causal_mission_feedback(
        as_of="2026-09-03T01:00:00Z", store=MemoryStore(memory)
    )

    assert result["missions"] == []
    assert result["rejected_hypothesis_ids"] == ["H-RUNTIME-1"]


def test_restart_produces_identical_missions(tmp_path, monkeypatch):
    registry = tmp_path / "rejected.json"
    registry.write_text('{"entries": []}', encoding="utf-8")
    monkeypatch.setattr(runtime, "REJECTED_REGISTRY_PATH", registry)
    memory = qualified_memory()
    restored = CausalRepricingMemory.from_document(memory.to_document())

    first = runtime.causal_mission_feedback(
        as_of="2026-09-03T01:00:00Z", store=MemoryStore(memory)
    )
    second = runtime.causal_mission_feedback(
        as_of="2026-09-03T01:00:00Z", store=MemoryStore(restored)
    )

    assert first == second


def test_backend_failure_is_explicit_and_fail_closed(tmp_path, monkeypatch):
    registry = tmp_path / "rejected.json"
    registry.write_text('{"entries": []}', encoding="utf-8")
    monkeypatch.setattr(runtime, "REJECTED_REGISTRY_PATH", registry)

    result = runtime.causal_mission_feedback(
        as_of="2026-09-03T01:00:00Z",
        store=MemoryStore(CausalMemoryError("secret transport detail")),
    )

    assert result["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert result["missions"] == []
    assert "secret transport detail" not in json.dumps(result)
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["oos_opening_authority"] is False


def test_unconfigured_backend_is_explicit_and_fail_closed(monkeypatch):
    monkeypatch.setattr(runtime.db, "configured", lambda: False)

    result = runtime.causal_mission_feedback(as_of="2026-09-03T01:00:00Z")

    assert result["status"] == "WAIT_MEMORY_NOT_CONFIGURED"
    assert result["missions"] == []

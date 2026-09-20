from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EpistemicClaim,
    EvidenceEvent,
    FrozenHypothesis,
    PointInTimeObservation,
    ReplayConflictError,
)


def _observation(
    observation_id: str,
    metric_name: str = "flow_24h",
    value: float = 20.0,
    *,
    observed_at: str = "2026-09-01T00:00:00Z",
    available_at: str = "2026-09-01T01:00:00Z",
    retrieved_at: str = "2026-09-01T02:00:00Z",
    subject_id: str = "BTC-USD",
    currency: str = "USD",
    measurement_window_hours: int = 24,
    venue: str = "coinbase",
    max_age_hours: int = 72,
) -> PointInTimeObservation:
    return PointInTimeObservation(
        observation_id=observation_id,
        metric_name=metric_name,
        value=value,
        unit="usd",
        observed_at=observed_at,
        available_at=available_at,
        retrieved_at=retrieved_at,
        source_id="test-source",
        revision_id="r1",
        provenance_uri="source://fixture",
        subject_id=subject_id,
        currency=currency,
        measurement_window_hours=measurement_window_hours,
        venue=venue,
        max_age_hours=max_age_hours,
    )


def _hypothesis(source_ids=("flow",)) -> FrozenHypothesis:
    return FrozenHypothesis(
        hypothesis_id="H1",
        statement="Flow large relative to float creates short-horizon upward repricing pressure.",
        mechanism_chain=("net_flow", "relative_scarcity", "repricing"),
        direction="positive",
        horizon_hours=72,
        falsifier="matched-control excess return <= 0 after costs",
        matched_controls=("market_beta", "volatility_regime"),
        lanes=("big_move", "strategy_component"),
        created_at="2026-09-02T00:00:00Z",
        source_observation_ids=tuple(source_ids),
        family_id="FLOW-SCARCITY-001",
        evaluation_method="matched_control_mean_difference_v1",
        family_size=2,
        alpha=0.05,
    )


def _support(event_id="support-1", evaluated_at="2026-09-03T00:00:00Z") -> EvidenceEvent:
    return EvidenceEvent(
        event_id=event_id,
        hypothesis_id="H1",
        evaluated_at=evaluated_at,
        kind="support",
        matched_controls=("market_beta", "volatility_regime"),
        outcome_observation_ids=tuple(
            "outcome" if index == 1 else f"outcome-{index}"
            for index in range(1, 7)
        ),
        control_observation_ids=tuple(
            "control" if index == 1 else f"control-{index}"
            for index in range(1, 7)
        ),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=6,
        confirmatory=True,
        p_value=0.015625,
    )


def _memory_with_hypothesis(*, half_life_days=30.0) -> CausalRepricingMemory:
    memory = CausalRepricingMemory(half_life_days=half_life_days)
    memory.register_observation(_observation("flow"))
    memory.register_hypothesis(_hypothesis())
    memory.register_observation(
        _observation(
            "outcome",
            "forward_return_72h",
            0.08,
            observed_at="2026-09-02T01:00:00Z",
            available_at="2026-09-02T04:00:00Z",
            retrieved_at="2026-09-02T05:00:00Z",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    memory.register_observation(
        _observation(
            "control",
            "matched_control_return_72h",
            0.01,
            observed_at="2026-09-02T01:00:00Z",
            available_at="2026-09-02T04:00:00Z",
            retrieved_at="2026-09-02T05:00:00Z",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    memory.register_observation(
        _observation(
            "adverse-outcome",
            "forward_return_72h",
            -0.08,
            observed_at="2026-09-03T01:00:00Z",
            available_at="2026-09-03T04:00:00Z",
            retrieved_at="2026-09-03T05:00:00Z",
            subject_id="BTC-USD-CONTRADICTION",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    memory.register_observation(
        _observation(
            "adverse-control",
            "matched_control_return_72h",
            0.01,
            observed_at="2026-09-03T01:00:00Z",
            available_at="2026-09-03T04:00:00Z",
            retrieved_at="2026-09-03T05:00:00Z",
            subject_id="BTC-USD-CONTRADICTION",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    _register_paired_evaluation(memory)
    return memory


def _register_paired_evaluation(
    memory: CausalRepricingMemory, *, pair_count: int = 6
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    outcome_ids = ["outcome"]
    control_ids = ["control"]
    for index in range(2, pair_count + 1):
        outcome_id = f"outcome-{index}"
        control_id = f"control-{index}"
        memory.register_observation(
            _observation(
                outcome_id,
                "forward_return_72h",
                0.08 + index / 10_000,
                observed_at="2026-09-02T01:00:00Z",
                available_at="2026-09-02T04:00:00Z",
                retrieved_at="2026-09-02T05:00:00Z",
                subject_id=f"BTC-USD-{index}",
                currency="ratio",
                measurement_window_hours=72,
            )
        )
        memory.register_observation(
            _observation(
                control_id,
                "matched_control_return_72h",
                0.01,
                observed_at="2026-09-02T01:00:00Z",
                available_at="2026-09-02T04:00:00Z",
                retrieved_at="2026-09-02T05:00:00Z",
                subject_id=f"BTC-USD-{index}",
                currency="ratio",
                measurement_window_hours=72,
            )
        )
        outcome_ids.append(outcome_id)
        control_ids.append(control_id)
    return tuple(outcome_ids), tuple(control_ids)


def test_confirmatory_support_recomputes_p_value_from_bound_pairs():
    memory = _memory_with_hypothesis()
    invented = EvidenceEvent(
        **{
            **_support("invented-significance").__dict__,
            "outcome_observation_ids": ("outcome",),
            "control_observation_ids": ("control",),
            "sample_size": 1,
            "p_value": 1e-9,
        }
    )

    with pytest.raises(CausalMemoryError, match="recomputed p_value"):
        memory.record_evidence(invented)


def test_confirmatory_support_rejects_inflated_sample_size():
    memory = _memory_with_hypothesis()

    with pytest.raises(CausalMemoryError, match="sample_size must equal"):
        memory.record_evidence(
            EvidenceEvent(
                **{
                    **_support("inflated-sample-size").__dict__,
                    "sample_size": 40,
                }
            )
        )


def test_confirmatory_support_rejects_cosmetic_ids_for_one_economic_unit():
    memory = _memory_with_hypothesis()
    outcome_ids = ["outcome"]
    control_ids = ["control"]
    for index in range(2, 7):
        for prefix, value in (("clone-outcome", 0.08), ("clone-control", 0.01)):
            observation_id = f"{prefix}-{index}"
            memory.register_observation(
                _observation(
                    observation_id,
                    "renamed_metric",
                    value,
                    observed_at="2026-09-02T01:00:00Z",
                    available_at="2026-09-02T04:00:00Z",
                    retrieved_at="2026-09-02T05:00:00Z",
                    currency="ratio",
                    measurement_window_hours=72,
                )
            )
            (outcome_ids if prefix == "clone-outcome" else control_ids).append(
                observation_id
            )
    pseudoreplicated = EvidenceEvent(
        **{
            **_support("pseudoreplicated-support").__dict__,
            "outcome_observation_ids": tuple(outcome_ids),
            "control_observation_ids": tuple(control_ids),
        }
    )

    with pytest.raises(CausalMemoryError, match="independent economic units"):
        memory.record_evidence(pseudoreplicated)


def test_evidence_event_rejects_duplicate_and_cross_side_observation_ids():
    with pytest.raises(CausalMemoryError, match="cannot contain duplicates"):
        EvidenceEvent(
            **{
                **_support("duplicate-ids").__dict__,
                "outcome_observation_ids": ("outcome", "outcome"),
                "control_observation_ids": ("control", "control-2"),
                "sample_size": 2,
            }
        )

    with pytest.raises(CausalMemoryError, match="must be disjoint"):
        EvidenceEvent(
            **{
                **_support("cross-side-id").__dict__,
                "outcome_observation_ids": ("shared",),
                "control_observation_ids": ("shared",),
                "sample_size": 1,
            }
        )


def test_cosmetic_clone_ids_cannot_reuse_units_across_evidence_events():
    memory = _memory_with_hypothesis()
    original = _support("original-unit-evidence")
    memory.record_evidence(original)
    cloned_outcomes = []
    cloned_controls = []
    for side, source_ids, destination in (
        ("outcome", original.outcome_observation_ids, cloned_outcomes),
        ("control", original.control_observation_ids, cloned_controls),
    ):
        for index, source_id in enumerate(source_ids, start=1):
            source = memory.observations[source_id]
            clone_id = f"cosmetic-{side}-{index}"
            memory.register_observation(
                PointInTimeObservation(
                    **{
                        **source.__dict__,
                        "observation_id": clone_id,
                        "metric_name": f"renamed-{side}",
                        "source_id": f"renamed-source-{index}",
                        "provenance_uri": f"clone://{clone_id}",
                    }
                )
            )
            destination.append(clone_id)
    cloned = EvidenceEvent(
        **{
            **original.__dict__,
            "event_id": "cosmetic-clone-unit-evidence",
            "outcome_observation_ids": tuple(cloned_outcomes),
            "control_observation_ids": tuple(cloned_controls),
        }
    )

    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        memory.record_evidence(cloned)


def test_confirmatory_support_rejects_mismatched_paired_unit_identity():
    memory = _memory_with_hypothesis()
    memory.register_observation(
        _observation(
            "mismatched-control",
            "matched_control_return_72h",
            0.01,
            observed_at="2026-09-05T01:00:00Z",
            available_at="2026-09-08T02:00:00Z",
            retrieved_at="2026-09-08T03:00:00Z",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    event = EvidenceEvent(
        **{
            **_support("mismatched-unit").__dict__,
            "outcome_observation_ids": ("outcome",),
            "control_observation_ids": ("mismatched-control",),
            "sample_size": 1,
            "confirmatory": False,
            "p_value": None,
            "evaluated_at": "2026-09-09T00:00:00Z",
        }
    )

    with pytest.raises(CausalMemoryError, match="same economic unit"):
        memory.record_evidence(event)


def test_confirmatory_support_rejects_overlapping_temporal_units():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))
    memory.register_hypothesis(_hypothesis())
    outcome_ids = []
    control_ids = []
    for index in range(1, 3):
        observed_at = f"2026-09-{5 + index:02d}T12:00:00Z"
        for prefix, value in (("overlap-outcome", 0.08), ("overlap-control", 0.01)):
            observation_id = f"{prefix}-{index}"
            memory.register_observation(
                _observation(
                    observation_id,
                    "forward_return_72h",
                    value,
                    observed_at=observed_at,
                    available_at=f"2026-09-{8 + index:02d}T13:00:00Z",
                    retrieved_at=f"2026-09-{8 + index:02d}T14:00:00Z",
                    currency="ratio",
                    measurement_window_hours=72,
                )
            )
            (outcome_ids if prefix == "overlap-outcome" else control_ids).append(
                observation_id
            )
    event = EvidenceEvent(
        **{
            **_support("overlapping-units").__dict__,
            "outcome_observation_ids": tuple(outcome_ids),
            "control_observation_ids": tuple(control_ids),
            "sample_size": 2,
            "confirmatory": False,
            "p_value": None,
            "evaluated_at": "2026-09-12T00:00:00Z",
        }
    )

    with pytest.raises(CausalMemoryError, match="non-overlapping"):
        memory.record_evidence(event)


def test_confirmatory_support_rejects_unsupported_evaluation_method():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))
    hypothesis = FrozenHypothesis(
        **{
            **_hypothesis().__dict__,
            "evaluation_method": "caller_supplied_regression_v1",
        }
    )
    memory.register_hypothesis(hypothesis)
    for observation_id, value in (("outcome", 0.08), ("control", 0.01)):
        memory.register_observation(
            _observation(
                observation_id,
                "forward_return_72h",
                value,
                observed_at="2026-09-02T01:00:00Z",
                available_at="2026-09-02T04:00:00Z",
                retrieved_at="2026-09-02T05:00:00Z",
                currency="ratio",
                measurement_window_hours=72,
            )
        )
    event = EvidenceEvent(
        **{
            **_support("unsupported-method").__dict__,
            "evaluation_method": "caller_supplied_regression_v1",
            "outcome_observation_ids": ("outcome",),
            "control_observation_ids": ("control",),
            "sample_size": 1,
            "p_value": 0.5,
        }
    )

    with pytest.raises(CausalMemoryError, match="unsupported confirmatory evaluation method"):
        memory.record_evidence(event)


def test_verified_evaluation_is_provenance_bound_and_stable_across_restart(tmp_path):
    memory = _memory_with_hypothesis()
    outcome_ids, control_ids = _register_paired_evaluation(memory)
    event = EvidenceEvent(
        **{
            **_support("verified-support").__dict__,
            "outcome_observation_ids": outcome_ids,
            "control_observation_ids": control_ids,
            "sample_size": 6,
            "p_value": 0.015625,
        }
    )
    assert memory.record_evidence(event) is True
    artifact = memory.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    )
    assert artifact is not None
    evidence = artifact["evidence_events"][0]
    assert evidence["verified_p_value"] == pytest.approx(0.015625)
    assert evidence["evaluation_implementation"] == (
        "paired-sign-exact-independent-units-v2"
    )
    assert evidence["independent_unit_contract"] == "material-unit-nonoverlap-v1"
    assert len(evidence["independent_units"]) == 6
    assert evidence["event_fingerprint"].startswith("mi-verified-evidence-v2:")

    path = tmp_path / "verified-memory.json"
    memory.save(path)
    restored = CausalRepricingMemory.load(path)
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) == artifact

    conflicting = EvidenceEvent(**{**event.__dict__, "p_value": 0.5})
    with pytest.raises(ReplayConflictError):
        restored.record_evidence(conflicting)


def test_legacy_caller_asserted_significance_loads_as_unverified_not_confirmatory():
    memory = _memory_with_hypothesis()
    memory.record_evidence(_support("legacy-support"))
    document = memory.to_document()
    document.pop("content_digest")
    event = document["events"][0]
    event.pop("evaluation_implementation")
    event["outcome_observation_ids"] = ["outcome"]
    event["control_observation_ids"] = ["control"]
    event["sample_size"] = 40
    event["p_value"] = 0.01
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()

    restored = CausalRepricingMemory.from_document(document)

    assert restored.events["legacy-support"].confirmatory is False
    assert restored.events["legacy-support"].p_value is None
    assert restored.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) is None
    assert CausalRepricingMemory.from_document(restored.to_document()).to_document() == (
        restored.to_document()
    )


def test_system_retrieval_time_blocks_late_backfill_from_earlier_decisions():
    memory = CausalRepricingMemory()
    memory.register_observation(
        _observation(
            "late",
            available_at="2026-09-01T01:00:00Z",
            retrieved_at="2026-09-05T00:00:00Z",
        )
    )
    assert memory.latest_metric("flow_24h", as_of="2026-09-02T00:00:00Z") is None

    with pytest.raises(CausalMemoryError, match="retrieved"):
        memory.register_claim(
            EpistemicClaim(
                claim_id="late-claim",
                level="fact",
                text="This backfill was not in the system yet.",
                created_at="2026-09-02T00:00:00Z",
                source_observation_ids=("late",),
            )
        )


def test_confirmatory_evidence_cannot_reuse_formation_or_pre_freeze_observations():
    memory = _memory_with_hypothesis()
    circular = EvidenceEvent(
        event_id="circular",
        hypothesis_id="H1",
        evaluated_at="2026-09-03T00:00:00Z",
        kind="support",
        matched_controls=("market_beta", "volatility_regime"),
        outcome_observation_ids=("flow",),
        control_observation_ids=("control",),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=40,
        p_value=0.01,
    )
    with pytest.raises(CausalMemoryError, match="formation"):
        memory.record_evidence(circular)

    memory.register_observation(
        _observation(
            "old-outcome",
            "forward_return_72h",
            0.08,
            observed_at="2026-09-01T03:00:00Z",
            available_at="2026-09-01T04:00:00Z",
            retrieved_at="2026-09-01T05:00:00Z",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    pre_freeze = EvidenceEvent(
        **{
            **_support("pre-freeze").__dict__,
            "outcome_observation_ids": ("old-outcome",),
        }
    )
    with pytest.raises(CausalMemoryError, match="after hypothesis freeze"):
        memory.record_evidence(pre_freeze)


def test_evidence_label_must_match_observed_direction_against_controls():
    memory = _memory_with_hypothesis()
    memory.register_observation(
        _observation(
            "losing-outcome",
            "forward_return_72h",
            -0.08,
            observed_at="2026-09-02T01:00:00Z",
            available_at="2026-09-02T04:00:00Z",
            retrieved_at="2026-09-02T05:00:00Z",
            currency="ratio",
            measurement_window_hours=72,
        )
    )
    mislabeled = EvidenceEvent(
        **{
            **_support("mislabeled").__dict__,
            "outcome_observation_ids": ("losing-outcome",),
        }
    )
    with pytest.raises(CausalMemoryError, match="observed effect direction"):
        memory.record_evidence(mislabeled)


def test_evidence_weight_is_bounded_and_derived_not_caller_controlled():
    memory = _memory_with_hypothesis()
    event = _support()
    assert not hasattr(event, "weight")
    memory.record_evidence(event)
    snapshot = memory.confidence("H1", as_of=event.evaluated_at)
    assert snapshot.decayed_net_evidence == pytest.approx(1.0)

    duplicate_test = EvidenceEvent(
        **{**event.__dict__, "event_id": "support-duplicate"}
    )
    with pytest.raises(CausalMemoryError, match="evaluation observations already consumed"):
        memory.record_evidence(duplicate_test)


def test_evidence_reuse_guard_is_order_insensitive_for_observation_sets():
    memory = _memory_with_hypothesis()
    first = _support("multi-source")
    memory.record_evidence(first)
    reordered = EvidenceEvent(
        **{
            **first.__dict__,
            "event_id": "multi-source-reordered",
            "outcome_observation_ids": tuple(reversed(first.outcome_observation_ids)),
            "control_observation_ids": tuple(reversed(first.control_observation_ids)),
        }
    )
    with pytest.raises(CausalMemoryError, match="evaluation observations already consumed"):
        memory.record_evidence(reordered)


def test_point_in_time_chronology_and_narrative_separation_fail_closed():
    with pytest.raises(CausalMemoryError):
        _observation(
            "bad",
            observed_at="2026-09-02T00:00:00Z",
            available_at="2026-09-01T00:00:00Z",
        )

    with pytest.raises(CausalMemoryError):
        EpistemicClaim(
            claim_id="story",
            level="hypothesis",  # type: ignore[arg-type]
            text="A compelling narrative is not a frozen hypothesis.",
            created_at="2026-09-02T00:00:00Z",
            source_observation_ids=("flow",),
        )

    memory = _memory_with_hypothesis()
    memory.register_observation(
        _observation(
            "future",
            available_at="2026-09-05T00:00:00Z",
            retrieved_at="2026-09-05T01:00:00Z",
        )
    )
    future_event = EvidenceEvent(
        event_id="future-evidence",
        hypothesis_id="H1",
        evaluated_at="2026-09-04T00:00:00Z",
        kind="contradiction",
        matched_controls=("market_beta", "volatility_regime"),
        outcome_observation_ids=("future",),
        control_observation_ids=("control",),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=40,
    )
    with pytest.raises(CausalMemoryError, match="point-in-time available"):
        memory.record_evidence(future_event)


def test_hypothesis_is_frozen_fingerprinted_and_exact_rejection_is_vetoed():
    hypothesis = _hypothesis()
    with pytest.raises(FrozenInstanceError):
        hypothesis.statement = "post-hoc rewrite"  # type: ignore[misc]

    memory = CausalRepricingMemory(rejected_fingerprints={hypothesis.fingerprint})
    memory.register_observation(_observation("flow"))
    with pytest.raises(CausalMemoryError, match="rejected"):
        memory.register_hypothesis(hypothesis)

    same_design_later = FrozenHypothesis(
        **{**hypothesis.__dict__, "created_at": "2026-09-10T00:00:00Z"}
    )
    assert same_design_later.fingerprint == hypothesis.fingerprint


def test_matched_controls_and_multiple_testing_are_predeclared_not_post_hoc():
    memory = _memory_with_hypothesis()
    wrong_controls = EvidenceEvent(
        event_id="wrong-controls",
        hypothesis_id="H1",
        evaluated_at="2026-09-03T00:00:00Z",
        kind="support",
        matched_controls=("market_beta",),
        outcome_observation_ids=("outcome",),
        control_observation_ids=("control",),
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=40,
        p_value=0.01,
    )
    with pytest.raises(CausalMemoryError, match="exactly match"):
        memory.record_evidence(wrong_controls)

    weak_after_family_adjustment = EvidenceEvent(
        event_id="weak-p",
        hypothesis_id="H1",
        evaluated_at="2026-09-03T00:00:00Z",
        kind="support",
        matched_controls=("market_beta", "volatility_regime"),
        outcome_observation_ids=_support().outcome_observation_ids[:5],
        control_observation_ids=_support().control_observation_ids[:5],
        evaluation_method="matched_control_mean_difference_v1",
        sample_size=5,
        p_value=0.03125,
    )
    with pytest.raises(CausalMemoryError, match="Bonferroni"):
        memory.record_evidence(weak_after_family_adjustment)

    exploratory = EvidenceEvent(
        event_id="exploratory",
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
    memory.record_evidence(exploratory)
    snapshot = memory.confidence("H1", as_of="2026-09-03T00:00:00Z")
    assert snapshot.score == 0.5
    assert snapshot.confirmatory_support_count == 0


def test_family_size_cannot_undercount_registered_sibling_hypotheses():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))

    first = FrozenHypothesis(**{**_hypothesis().__dict__, "family_size": 1})
    assert memory.register_hypothesis(first) is True

    sibling = FrozenHypothesis(
        **{
            **first.__dict__,
            "hypothesis_id": "H2",
            "statement": (
                "A sibling flow-scarcity test must share the complete family correction."
            ),
        }
    )
    with pytest.raises(CausalMemoryError, match="family_size cannot undercount"):
        memory.register_hypothesis(sibling)

    assert tuple(memory.hypotheses) == ("H1",)


def test_family_size_allows_predeclared_sibling_hypotheses():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))

    first = _hypothesis()
    sibling = FrozenHypothesis(
        **{
            **first.__dict__,
            "hypothesis_id": "H2",
            "statement": "A distinct predeclared sibling flow-scarcity test.",
        }
    )

    assert memory.register_hypothesis(first) is True
    assert memory.register_hypothesis(sibling) is True


def test_confidence_can_gain_lose_and_decay_toward_neutral():
    memory = _memory_with_hypothesis(half_life_days=10.0)
    memory.record_evidence(_support())
    after_support = memory.confidence("H1", as_of="2026-09-03T00:00:00Z")
    assert after_support.score > 0.5

    memory.record_evidence(
        EvidenceEvent(
            event_id="contradiction-1",
            hypothesis_id="H1",
            evaluated_at="2026-09-04T00:00:00Z",
            kind="contradiction",
            matched_controls=("market_beta", "volatility_regime"),
            outcome_observation_ids=("adverse-outcome",),
            control_observation_ids=("adverse-control",),
            evaluation_method="matched_control_mean_difference_v1",
            sample_size=1,
        )
    )
    after_contradiction = memory.confidence("H1", as_of="2026-09-04T00:00:00Z")
    assert after_contradiction.score < 0.5
    assert len(memory.contradiction_ledger("H1")) == 1

    much_later = memory.confidence("H1", as_of="2027-03-04T00:00:00Z")
    assert abs(much_later.score - 0.5) < abs(after_contradiction.score - 0.5)


def test_replay_is_idempotent_but_conflicting_same_id_fails_closed():
    memory = _memory_with_hypothesis()
    event = _support()
    assert memory.record_evidence(event) is True
    assert memory.record_evidence(event) is False

    conflicting = EvidenceEvent(
        **{**event.__dict__, "note": "changed after the fact"}
    )
    with pytest.raises(ReplayConflictError):
        memory.record_evidence(conflicting)


def test_flow_relative_impact_requires_point_in_time_denominator():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow", "flow_24h", 20.0))
    missing = memory.relative_impact(
        ratio_name="flow_float",
        numerator_metric="flow_24h",
        denominator_metric="float_usd",
        subject_id="BTC-USD",
        as_of="2026-09-02T00:00:00Z",
    )
    assert missing.value is None
    assert missing.reason == "point_in_time_input_unavailable"

    memory.register_observation(_observation("float", "float_usd", 100.0))
    available = memory.relative_impact(
        ratio_name="flow_float",
        numerator_metric="flow_24h",
        denominator_metric="float_usd",
        subject_id="BTC-USD",
        as_of="2026-09-02T00:00:00Z",
    )
    assert available.value == pytest.approx(0.2)

    memory.register_observation(
        _observation(
            "future-liquidity",
            "liquidity_usd",
            50.0,
            observed_at="2026-09-04T00:00:00Z",
            available_at="2026-09-05T00:00:00Z",
            retrieved_at="2026-09-05T01:00:00Z",
        )
    )
    unavailable = memory.relative_impact(
        ratio_name="flow_liquidity",
        numerator_metric="flow_24h",
        denominator_metric="liquidity_usd",
        subject_id="BTC-USD",
        as_of="2026-09-04T00:00:00Z",
    )
    assert unavailable.value is None


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"subject_id": "ETH-USD"}, "subject_mismatch"),
        ({"currency": "EUR"}, "currency_or_unit_mismatch"),
        ({"measurement_window_hours": 1}, "measurement_window_mismatch"),
        ({"venue": "kraken"}, "venue_mismatch"),
    ],
)
def test_relative_impact_rejects_incomparable_inputs(override, reason):
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow", "flow_24h", 20.0))
    memory.register_observation(
        _observation("float", "float_usd", 100.0, **override)
    )
    ratio = memory.relative_impact(
        ratio_name="flow_float",
        numerator_metric="flow_24h",
        denominator_metric="float_usd",
        subject_id="BTC-USD",
        as_of="2026-09-02T00:00:00Z",
    )
    assert ratio.value is None
    assert ratio.reason == reason


def test_relative_impact_rejects_stale_inputs():
    memory = CausalRepricingMemory()
    memory.register_observation(
        _observation("flow", "flow_24h", 20.0, max_age_hours=1)
    )
    memory.register_observation(
        _observation("float", "float_usd", 100.0, max_age_hours=1)
    )
    ratio = memory.relative_impact(
        ratio_name="flow_float",
        numerator_metric="flow_24h",
        denominator_metric="float_usd",
        subject_id="BTC-USD",
        as_of="2026-09-02T00:00:00Z",
    )
    assert ratio.value is None
    assert ratio.reason == "stale_input"


def test_relative_impact_selects_latest_metric_within_requested_subject():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("btc-flow", "flow_24h", 20.0))
    memory.register_observation(_observation("btc-float", "float_usd", 100.0))
    for observation_id, metric_name, value in (
        ("eth-flow", "flow_24h", 90.0),
        ("eth-float", "float_usd", 300.0),
    ):
        memory.register_observation(
            _observation(
                observation_id,
                metric_name,
                value,
                subject_id="ETH-USD",
                observed_at="2026-09-01T03:00:00Z",
                available_at="2026-09-01T04:00:00Z",
                retrieved_at="2026-09-01T05:00:00Z",
            )
        )

    ratio = memory.relative_impact(
        ratio_name="flow_float",
        numerator_metric="flow_24h",
        denominator_metric="float_usd",
        subject_id="BTC-USD",
        as_of="2026-09-02T00:00:00Z",
    )
    assert ratio.reason == "ok"
    assert ratio.numerator_observation_id == "btc-flow"
    assert ratio.denominator_observation_id == "btc-float"
    assert ratio.value == pytest.approx(0.2)


def test_supported_finding_can_feed_research_lanes_but_has_zero_authority():
    memory = _memory_with_hypothesis()
    memory.record_evidence(_support())
    artifact = memory.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    )
    assert artifact is not None
    assert artifact["research_only"] is True
    assert artifact["trading_authority"] is False
    assert artifact["promotion_authority"] is False
    assert artifact["oos_opening_authority"] is False
    assert artifact["frozen_test_contract"] == {
        "falsifier": "matched-control excess return <= 0 after costs",
        "matched_controls": ["market_beta", "volatility_regime"],
        "family_id": "FLOW-SCARCITY-001",
        "family_size": 2,
        "alpha": 0.05,
        "evaluation_method": "matched_control_mean_difference_v1",
        "direction": "positive",
        "horizon_hours": 72,
    }
    assert artifact["evidence_events"][0]["event_id"] == "support-1"
    assert artifact["evidence_events"][0]["event_fingerprint"]
    assert len(artifact["evidence_events"][0]["outcome_observation_ids"]) == 6
    assert len(artifact["evidence_events"][0]["control_observation_ids"]) == 6
    assert artifact["evidence_events"][0]["outcome_provenance_fingerprints"]
    assert artifact["evidence_events"][0]["control_provenance_fingerprints"]
    assert artifact["evidence_events"][0]["adjusted_p_value"] == pytest.approx(0.03125)

    memory.record_evidence(
        EvidenceEvent(
            event_id="contradiction-later",
            hypothesis_id="H1",
            evaluated_at="2026-09-04T00:00:00Z",
            kind="contradiction",
            matched_controls=("market_beta", "volatility_regime"),
            outcome_observation_ids=("adverse-outcome",),
            control_observation_ids=("adverse-control",),
            evaluation_method="matched_control_mean_difference_v1",
            sample_size=1,
        )
    )
    assert (
        memory.research_artifact(
            "H1", lane="strategy_component", as_of="2026-09-04T00:00:00Z"
        )
        is None
    )


def test_persistence_is_digest_verified_and_corruption_fails_closed(tmp_path):
    memory = _memory_with_hypothesis()
    memory.register_claim(
        EpistemicClaim(
            claim_id="inference-1",
            level="inference",
            text="Observed flow may transmit through relative scarcity.",
            created_at="2026-09-02T00:00:00Z",
            source_observation_ids=("flow",),
        )
    )
    memory.record_evidence(_support())
    path = tmp_path / "causal-memory.json"
    memory.save(path)

    restored = CausalRepricingMemory.load(path)
    assert restored.to_document() == memory.to_document()
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    )

    document = json.loads(path.read_text(encoding="utf-8"))
    document["events"][0]["note"] = "tampered without a new digest"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CausalMemoryError, match="digest"):
        CausalRepricingMemory.load(path)

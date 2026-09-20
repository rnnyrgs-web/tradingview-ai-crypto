from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import json

import pytest

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    EpistemicClaim,
    EvaluationPairContract,
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
    selection_contract_id: str = "",
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
        selection_contract_id=selection_contract_id,
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
        evaluation_units=tuple(
            (
                "BTC-USD" if index == 1 else f"BTC-USD-{index}",
                "2026-09-02T01:00:00Z",
                72,
            )
            for index in range(1, 7)
        ),
        evaluation_pairs=tuple(
            (
                "outcome" if index == 1 else f"outcome-{index}",
                "control" if index == 1 else f"control-{index}",
            )
            for index in range(1, 7)
        ),
        evaluation_pair_contracts=tuple(
            EvaluationPairContract(
                outcome_observation_id=(
                    "outcome" if index == 1 else f"outcome-{index}"
                ),
                control_observation_id=(
                    "control" if index == 1 else f"control-{index}"
                ),
                outcome_metric_name="forward_return_72h",
                outcome_source_id="test-source",
                outcome_provenance_uri="source://fixture",
                control_metric_name="matched_control_return_72h",
                control_source_id="test-source",
                control_provenance_uri="source://fixture",
                control_selection_contract_id="market-beta-volatility-v1",
            )
            for index in range(1, 7)
        ),
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
            selection_contract_id="market-beta-volatility-v1",
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
                selection_contract_id="market-beta-volatility-v1",
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


def _clone_evidence_units(
    memory: CausalRepricingMemory,
    original: EvidenceEvent,
    *,
    suffix: str,
    observation_changes: dict[str, object] | None = None,
    value_scale: float = 1.0,
    hypothesis_id: str | None = None,
    distinct_subjects: bool = False,
) -> EvidenceEvent:
    """Give the same realizations fresh observation/provenance labels."""
    changed = observation_changes or {}
    cloned_sides = []
    for side, source_ids in (
        ("outcome", original.outcome_observation_ids),
        ("control", original.control_observation_ids),
    ):
        new_ids = []
        for index, source_id in enumerate(source_ids, start=1):
            source = memory.observations[source_id]
            clone_id = f"{suffix}-{side}-{index}"
            source_changes = {
                "subject_id": f"{source.subject_id}-independent"
            } if distinct_subjects else {}
            memory.register_observation(
                replace(
                    source,
                    observation_id=clone_id,
                    value=source.value * value_scale,
                    source_id=f"{suffix}-source-{index}",
                    provenance_uri=f"clone://{clone_id}",
                    **source_changes,
                    **changed,
                )
            )
            new_ids.append(clone_id)
        cloned_sides.append(tuple(new_ids))
    return replace(
        original,
        event_id=f"{suffix}-event",
        hypothesis_id=hypothesis_id or original.hypothesis_id,
        outcome_observation_ids=cloned_sides[0],
        control_observation_ids=cloned_sides[1],
    )


@pytest.mark.parametrize(
    ("label", "changes", "value_scale"),
    [
        ("fresh-ids", {}, 1.0),
        ("currency", {"currency": "basis-points"}, 1.0),
        ("rescaled-unit", {"unit": "basis-points"}, 10_000.0),
        ("unit", {"unit": "display-ratio"}, 1.0),
        ("venue", {"venue": "relabeled-venue"}, 1.0),
        ("metric", {"metric_name": "cosmetic-return-label"}, 1.0),
        (
            "combined",
            {
                "currency": "basis-points",
                "unit": "basis-points",
                "venue": "relabeled-venue",
                "metric_name": "cosmetic-return-label",
            },
            10_000.0,
        ),
    ],
)
def test_representation_relabel_cannot_reconsume_economic_units(
    label, changes, value_scale
):
    memory = _memory_with_hypothesis()
    original = _support("original-economic-evidence")
    assert memory.record_evidence(original)
    clone = _clone_evidence_units(
        memory,
        original,
        suffix=label,
        observation_changes=changes,
        value_scale=value_scale,
    )
    if label == "combined":
        original_verification = memory._verified_evaluation(original, memory.hypotheses["H1"])
        clone_verification = memory._verified_evaluation(clone, memory.hypotheses["H1"])
        assert {
            unit["unit_fingerprint"] for unit in original_verification["independent_units"]
        } == {
            unit["unit_fingerprint"] for unit in clone_verification["independent_units"]
        }
        assert original_verification["verified_fingerprint"] != clone_verification["verified_fingerprint"]

    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        memory.record_evidence(clone)
    assert memory.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 1


def test_representation_relabel_cannot_reconsume_after_restart(tmp_path):
    memory = _memory_with_hypothesis()
    original = _support("original-before-restart")
    assert memory.record_evidence(original)
    path = tmp_path / "durable-memory.json"
    memory.save(path)
    restored = CausalRepricingMemory.load(path)
    clone = _clone_evidence_units(
        restored,
        original,
        suffix="restart-clone",
        observation_changes={"currency": "bp", "unit": "bp", "venue": "other"},
        value_scale=10_000.0,
    )

    assert restored.record_evidence(original) is False
    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        restored.record_evidence(clone)


def test_economic_unit_consumption_is_global_across_hypotheses_and_families():
    memory = _memory_with_hypothesis()
    second_hypothesis = replace(
        _hypothesis(), hypothesis_id="H2", family_id="OTHER-FAMILY",
        evaluation_units=(), evaluation_pairs=(), evaluation_pair_contracts=(),
    )
    memory.register_hypothesis(second_hypothesis)
    original = _support("first-hypothesis-evidence")
    assert memory.record_evidence(original)
    clone = _clone_evidence_units(
        memory,
        original,
        suffix="other-family-clone",
        observation_changes={"venue": "other"},
        hypothesis_id="H2",
    )

    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        memory.record_evidence(clone)
    assert memory.confidence(
        "H2", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0


def test_nonoverlapping_temporal_realizations_remain_independent():
    memory = _memory_with_hypothesis()
    original = _support("first-temporal-evidence")
    assert memory.record_evidence(original)
    later = _clone_evidence_units(
        memory,
        original,
        suffix="later-independent-window",
        observation_changes={
            "observed_at": "2026-09-06T01:00:00Z",
            "available_at": "2026-09-09T01:00:00Z",
            "retrieved_at": "2026-09-09T02:00:00Z",
        },
    )
    later = replace(later, evaluated_at="2026-09-09T03:00:00Z")

    with pytest.raises(CausalMemoryError, match="repeated confirmatory looks"):
        memory.record_evidence(later)
    assert memory.record_evidence(replace(later, confirmatory=False))
    assert memory.confidence(
        "H1", as_of="2026-09-09T03:00:00Z"
    ).confirmatory_support_count == 1


def test_distinct_cross_sectional_subjects_remain_independent():
    memory = _memory_with_hypothesis()
    original = _support("first-cross-section")
    assert memory.record_evidence(original)
    independent = _clone_evidence_units(
        memory,
        original,
        suffix="second-cross-section",
        distinct_subjects=True,
    )

    with pytest.raises(CausalMemoryError, match="repeated confirmatory looks"):
        memory.record_evidence(independent)
    assert memory.record_evidence(replace(independent, confirmatory=False))
    artifact = memory.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    )
    assert artifact is not None
    assert len(artifact["evidence_events"]) == 2
    assert [event["confirmatory"] for event in artifact["evidence_events"]] == [
        True,
        False,
    ]
    assert all(len(event["independent_units"]) == 6 for event in artifact["evidence_events"])


def test_overlapping_temporal_realization_cannot_reconsume_across_events():
    memory = _memory_with_hypothesis()
    original = _support("first-overlap-evidence")
    assert memory.record_evidence(original)
    overlapping = _clone_evidence_units(
        memory,
        original,
        suffix="overlapping-window",
        observation_changes={
            "observed_at": "2026-09-02T02:00:00Z",
            "available_at": "2026-09-05T02:00:00Z",
            "retrieved_at": "2026-09-05T03:00:00Z",
        },
    )
    overlapping = replace(overlapping, evaluated_at="2026-09-05T04:00:00Z")

    with pytest.raises(CausalMemoryError, match="independent units already consumed"):
        memory.record_evidence(overlapping)


@pytest.mark.parametrize("missing_field", ["subject_id", "source_id"])
def test_rehashed_durable_memory_missing_identity_or_provenance_fails_closed(
    missing_field,
):
    memory = _memory_with_hypothesis()
    assert memory.record_evidence(_support())
    document = memory.to_document()
    document["observations"][0].pop(missing_field)
    payload = {key: value for key, value in document.items() if key != "content_digest"}
    document["content_digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()

    with pytest.raises(CausalMemoryError, match="scientific-contract validation"):
        CausalRepricingMemory.from_document(document)


def test_rehashed_durable_memory_cannot_replay_representational_clone():
    memory = _memory_with_hypothesis()
    original = _support("durable-original")
    assert memory.record_evidence(original)
    clone = _clone_evidence_units(
        memory,
        original,
        suffix="forged-durable-clone",
        observation_changes={"currency": "bp", "unit": "bp", "venue": "other"},
        value_scale=10_000.0,
    )
    document = memory.to_document()
    document["events"].append(asdict(clone))
    payload = {key: value for key, value in document.items() if key != "content_digest"}
    document["content_digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()

    with pytest.raises(CausalMemoryError, match="scientific-contract validation"):
        CausalRepricingMemory.from_document(document)


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
    assert evidence["independent_unit_contract"] == "economic-realization-nonoverlap-v2"
    assert len(evidence["independent_units"]) == 6
    assert evidence["event_fingerprint"].startswith("mi-verified-evidence-v3:")

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
    hypothesis = replace(
        _hypothesis(),
        evaluation_units=(),
        evaluation_pairs=(),
        evaluation_pair_contracts=(),
    )
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
    weak_memory = CausalRepricingMemory()
    weak_memory.register_observation(memory.observations["flow"])
    weak_memory.register_hypothesis(
        replace(
            _hypothesis(),
            evaluation_units=_hypothesis().evaluation_units[:5],
            evaluation_pairs=_hypothesis().evaluation_pairs[:5],
            evaluation_pair_contracts=_hypothesis().evaluation_pair_contracts[:5],
        )
    )
    for source_id in (
        weak_after_family_adjustment.outcome_observation_ids
        + weak_after_family_adjustment.control_observation_ids
    ):
        weak_memory.register_observation(memory.observations[source_id])
    with pytest.raises(CausalMemoryError, match="Bonferroni"):
        weak_memory.record_evidence(weak_after_family_adjustment)

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


def test_distinct_family_labels_cannot_reset_project_wide_testing_budget():
    memory = _memory_with_hypothesis()
    assert memory.record_evidence(_support("first-family-support")) is True

    sibling = replace(
        _hypothesis(),
        hypothesis_id="H2",
        statement="A relabeled sibling of the same flow-scarcity search.",
        family_id="RENAMED-FLOW-SCARCITY",
        family_size=1,
        evaluation_units=tuple(
            (f"second-{subject}", start, window)
            for subject, start, window in _hypothesis().evaluation_units
        ),
        evaluation_pairs=tuple(
            (f"second-{outcome_id}", f"second-{control_id}")
            for outcome_id, control_id in _hypothesis().evaluation_pairs
        ),
        evaluation_pair_contracts=tuple(
            replace(
                contract,
                outcome_observation_id=f"second-{contract.outcome_observation_id}",
                control_observation_id=f"second-{contract.control_observation_id}",
            )
            for contract in _hypothesis().evaluation_pair_contracts
        ),
    )
    assert memory.register_hypothesis(sibling) is True
    original = _support()
    for source_id in original.outcome_observation_ids + original.control_observation_ids:
        observation = memory.observations[source_id]
        memory.register_observation(
            replace(
                observation,
                observation_id=f"second-{source_id}",
                subject_id=f"second-{observation.subject_id}",
            )
        )
    second = replace(
        original,
        event_id="second-family-support",
        hypothesis_id="H2",
        outcome_observation_ids=tuple(
            f"second-{source_id}" for source_id in original.outcome_observation_ids
        ),
        control_observation_ids=tuple(
            f"second-{source_id}" for source_id in original.control_observation_ids
        ),
    )
    with pytest.raises(CausalMemoryError, match="project-wide"):
        memory.record_evidence(second)
    restored = CausalRepricingMemory.from_document(memory.to_document())
    assert restored.hypothesis_order == ["H1", "H2"]
    with pytest.raises(CausalMemoryError, match="project-wide"):
        restored.record_evidence(second)


def test_confirmatory_evaluation_cannot_change_frozen_sample_or_look_again():
    memory = _memory_with_hypothesis()
    partial = replace(
        _support("sample-selected-after-outcomes"),
        outcome_observation_ids=_support().outcome_observation_ids[:5],
        control_observation_ids=_support().control_observation_ids[:5],
        sample_size=5,
        p_value=0.03125,
    )
    with pytest.raises(
        CausalMemoryError,
        match="frozen outcome/control pairs|frozen evaluation units",
    ):
        memory.record_evidence(partial)
    assert memory.record_evidence(_support("first-frozen-look"))
    later = _clone_evidence_units(
        memory,
        _support("first-frozen-look"),
        suffix="unplanned-later-look",
        distinct_subjects=True,
    )
    with pytest.raises(CausalMemoryError, match="repeated confirmatory looks"):
        memory.record_evidence(later)


def test_confirmatory_evidence_rejects_post_outcome_control_substitution():
    memory = _memory_with_hypothesis()
    replacement_ids = []
    for index, source_id in enumerate(_support().control_observation_ids, start=1):
        replacement_id = f"posthoc-control-{index}"
        replacement_ids.append(replacement_id)
        memory.register_observation(
            replace(
                memory.observations[source_id],
                observation_id=replacement_id,
                value=-1.0,
            )
        )

    attack = replace(
        _support("posthoc-control-substitution"),
        control_observation_ids=tuple(replacement_ids),
    )
    with pytest.raises(CausalMemoryError, match="frozen outcome/control pairs"):
        memory.record_evidence(attack)


def test_confirmatory_evidence_rejects_substituted_data_under_planned_control_ids():
    prepared = _memory_with_hypothesis()
    memory = CausalRepricingMemory()
    memory.register_observation(prepared.observations["flow"])
    memory.register_hypothesis(prepared.hypotheses["H1"])
    for outcome_id, control_id in prepared.hypotheses["H1"].evaluation_pairs:
        memory.register_observation(prepared.observations[outcome_id])
        memory.register_observation(
            replace(
                prepared.observations[control_id],
                metric_name="posthoc_selected_control",
                source_id="posthoc-selected-provider",
                provenance_uri=f"posthoc://{control_id}",
            )
        )

    with pytest.raises(CausalMemoryError, match="frozen control provenance"):
        memory.record_evidence(_support("planned-id-control-substitution"))


def test_evaluation_plan_cannot_be_registered_after_outcomes_are_present():
    memory = _memory_with_hypothesis()
    with pytest.raises(CausalMemoryError, match="after its economic units are observed"):
        memory.register_hypothesis(
            replace(_hypothesis(), hypothesis_id="LATE-PLAN", family_id="NEW-LABEL")
        )
    assert memory.register_hypothesis(_hypothesis()) is False


def test_adding_evaluation_plan_cannot_rescue_prior_rejected_design():
    legacy = replace(
        _hypothesis(),
        evaluation_units=(),
        evaluation_pairs=(),
        evaluation_pair_contracts=(),
    )
    memory = CausalRepricingMemory(rejected_fingerprints={legacy.fingerprint})
    memory.register_observation(_observation("flow"))
    with pytest.raises(CausalMemoryError, match="rejected"):
        memory.register_hypothesis(_hypothesis())


def test_adding_frozen_pairs_cannot_rescue_prior_rejected_planned_design():
    pre_pair_design = replace(
        _hypothesis(), evaluation_pairs=(), evaluation_pair_contracts=()
    )
    memory = CausalRepricingMemory(
        rejected_fingerprints={pre_pair_design.fingerprint}
    )
    memory.register_observation(_observation("flow"))

    with pytest.raises(CausalMemoryError, match="rejected"):
        memory.register_hypothesis(_hypothesis())


def test_adding_provenance_contracts_cannot_rescue_rejected_paired_design():
    pre_provenance_design = replace(
        _hypothesis(), evaluation_pair_contracts=()
    )
    memory = CausalRepricingMemory(
        rejected_fingerprints={pre_provenance_design.fingerprint}
    )
    memory.register_observation(_observation("flow"))

    with pytest.raises(CausalMemoryError, match="rejected"):
        memory.register_hypothesis(_hypothesis())


def test_rejected_planned_design_cannot_change_sample_schedule_to_reenter():
    memory = _memory_with_hypothesis()
    memory.reject_hypothesis("H1")
    shifted = replace(
        _hypothesis(),
        hypothesis_id="H2",
        evaluation_units=tuple(
            (subject, "2026-09-20T01:00:00Z", window)
            for subject, _, window in _hypothesis().evaluation_units
        ),
    )
    with pytest.raises(CausalMemoryError, match="rejected"):
        memory.register_hypothesis(shifted)


def test_legacy_family_only_document_loses_confirmatory_authority():
    memory = _memory_with_hypothesis()
    assert memory.record_evidence(_support("legacy-family-only"))
    document = memory.to_document()
    document.pop("content_digest")
    document.pop("project_testing_protocol")
    document.pop("hypothesis_order")
    document.pop("event_order")
    document.pop("registration_log")
    document["hypotheses"][0].pop("evaluation_units")
    document["hypotheses"][0].pop("evaluation_pairs")
    document["hypotheses"][0].pop("evaluation_pair_contracts")
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()
    restored = CausalRepricingMemory.from_document(document)
    assert restored.events["legacy-family-only"].confirmatory is False
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) is None
    assert CausalRepricingMemory.from_document(restored.to_document()).to_document() == (
        restored.to_document()
    )


def test_legacy_underdeclared_family_replays_without_admitting_a_new_sibling():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))
    for index in (1, 2):
        memory.register_hypothesis(replace(
            _hypothesis(), hypothesis_id=f"H{index}",
            statement=f"Historical family member {index}.",
            evaluation_units=(), evaluation_pairs=(), evaluation_pair_contracts=(),
        ))
    document = memory.to_document()
    for field in ("content_digest", "project_testing_protocol", "hypothesis_order", "event_order", "registration_log", "legacy_underdeclared_hypotheses"):
        document.pop(field)
    for index in (3, 4):
        sibling = dict(document["hypotheses"][0])
        sibling.update(hypothesis_id=f"H{index}", statement=f"Historical family member {index}.")
        document["hypotheses"].append(sibling)
    for sibling in document["hypotheses"]:
        sibling.pop("evaluation_units")
        sibling.pop("evaluation_pairs")
        sibling.pop("evaluation_pair_contracts")
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()

    restored = CausalRepricingMemory.from_document(document)
    assert len(restored.hypotheses) == 4
    assert CausalRepricingMemory.from_document(restored.to_document()).to_document() == restored.to_document()
    with pytest.raises(CausalMemoryError, match="family_size cannot undercount"):
        restored.register_hypothesis(replace(
            _hypothesis(), hypothesis_id="H5", statement="New undeclared sibling.",
            evaluation_units=(), evaluation_pairs=(), evaluation_pair_contracts=(),
        ))


def test_current_protocol_document_without_frozen_pairs_loses_confirmatory_authority():
    memory = _memory_with_hypothesis()
    assert memory.record_evidence(_support("pre-pair-contract-support"))
    document = memory.to_document()
    document.pop("content_digest")
    document["hypotheses"][0].pop("evaluation_pairs")
    document["hypotheses"][0].pop("evaluation_pair_contracts")
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()

    restored = CausalRepricingMemory.from_document(document)

    assert restored.events["pre-pair-contract-support"].confirmatory is False
    assert restored.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) is None


def test_current_protocol_document_without_pair_provenance_loses_confirmatory_authority():
    memory = _memory_with_hypothesis()
    assert memory.record_evidence(_support("pre-provenance-contract-support"))
    document = memory.to_document()
    document.pop("content_digest")
    document["hypotheses"][0].pop("evaluation_pair_contracts")
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()

    restored = CausalRepricingMemory.from_document(document)

    assert restored.events["pre-provenance-contract-support"].confirmatory is False
    assert restored.confidence(
        "H1", as_of="2026-09-03T00:00:00Z"
    ).confirmatory_support_count == 0
    assert restored.research_artifact(
        "H1", lane="big_move", as_of="2026-09-03T00:00:00Z"
    ) is None


def test_malformed_pair_document_cannot_coerce_string_into_observation_ids():
    memory = CausalRepricingMemory()
    memory.register_observation(_observation("flow"))
    memory.register_hypothesis(_hypothesis())
    document = memory.to_document()
    document.pop("content_digest")
    document["hypotheses"][0]["evaluation_pairs"] = [
        "OC", *document["hypotheses"][0]["evaluation_pairs"][1:]
    ]
    document["hypotheses"][0]["evaluation_pair_contracts"][0].update(
        outcome_observation_id="O",
        control_observation_id="C",
    )
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    document["content_digest"] = hashlib.sha256(encoded).hexdigest()

    with pytest.raises(CausalMemoryError, match="scientific-contract validation"):
        CausalRepricingMemory.from_document(document)


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
        "project_testing_protocol": "global-sequential-bonferroni-v1",
        "project_test_slot": 1,
        "project_alpha": 0.05,
        "confirmatory_p_threshold": 0.025,
        "evaluation_units": [list(unit) for unit in _hypothesis().evaluation_units],
        "evaluation_pairs": [list(pair) for pair in _hypothesis().evaluation_pairs],
        "evaluation_pair_contracts": [
            asdict(contract) for contract in _hypothesis().evaluation_pair_contracts
        ],
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

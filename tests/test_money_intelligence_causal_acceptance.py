from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import pytest

import money_intelligence_causal_acceptance as acceptance
from money_intelligence_causal_memory import CausalMemoryError, CausalRepricingMemory
from money_intelligence_mission_integration import apply_causal_feedback


def test_runtime_acceptance_rechecks_deployment_packaging_changes():
    workflow = Path(
        ".github/workflows/money-intelligence-causal-runtime-acceptance.yml"
    ).read_text(encoding="utf-8")

    assert "      - Dockerfile" in workflow
    assert "  schedule:" in workflow
    assert "Prospective guard passed; full synthetic runtime acceptance remains pending" in workflow


def test_fixture_subject_is_unique_for_each_full_deployed_sha():
    first = acceptance._ids("a" * 16 + "b" * 24)
    second = acceptance._ids("a" * 16 + "c" * 24)
    assert first["hypothesis"] != second["hypothesis"]
    assert acceptance._fixture_subject(first["hypothesis"]) != acceptance._fixture_subject(
        second["hypothesis"]
    )


@pytest.mark.parametrize("prior_slots", [4, 28])
def test_acceptance_fixture_can_confirm_after_prior_project_tests(prior_slots):
    ids = acceptance._ids("b" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    memory = CausalRepricingMemory()
    memory.register_observation(acceptance._observation(
        ids["formation"], metric_name="flow_intensity", value=10.0,
        observed_at=base, available_at=base + timedelta(minutes=1), window_hours=1,
    ))
    for index in range(prior_slots):
        memory.register_hypothesis(replace(
            acceptance._contract(ids, base),
            hypothesis_id=f"prior-{index}", family_id=f"prior-family-{index}",
            family_size=1, evaluation_units=(), evaluation_pairs=(),
            evaluation_selectors=(),
        ))
    memory.register_observation(replace(
        acceptance._observation(
            ids["support_outcome_1"], metric_name="matched_return", value=1.0,
            observed_at=base + timedelta(hours=1),
            available_at=base + timedelta(hours=2, minutes=1), window_hours=1,
        ),
        observation_id="legacy-overlap", subject_id="PHASE2_ACCEPTANCE",
        provenance_uri="acceptance://legacy-overlap",
    ))
    acceptance._seed_support(memory, ids, base)
    hypothesis = memory.hypotheses[ids["hypothesis"]]
    verification = memory._verified_evaluation(memory.events[ids["support"]], hypothesis)
    assert len(hypothesis.evaluation_units) == verification["sample_size"]
    assert hypothesis.evaluation_pairs == tuple(
        (ids[f"support_outcome_{index}"], ids[f"support_control_{index}"])
        for index in range(1, verification["sample_size"] + 1)
    )
    assert hypothesis.evaluation_selectors == tuple(
        (
            (
                "matched_return", "phase2-runtime-acceptance-fixture",
                f"acceptance://{ids[f'support_outcome_{index}']}",
            ),
            (
                "matched_return", "phase2-runtime-acceptance-fixture",
                f"acceptance://{ids[f'support_control_{index}']}",
            ),
        )
        for index in range(1, verification["sample_size"] + 1)
    )
    if prior_slots == 28:
        assert len(hypothesis.evaluation_units) > acceptance.SUPPORT_PAIRS
    assert verification["verified_p_value"] <= memory._project_threshold(hypothesis)


class FakeDurableCausalStore:
    _lock = Lock()
    _document = CausalRepricingMemory().to_document()

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._document = CausalRepricingMemory().to_document()

    @staticmethod
    def document_to_memory(document):
        try:
            return CausalRepricingMemory.from_document(document)
        except CausalMemoryError as exc:
            raise CausalMemoryError("fake durable causal memory integrity failure") from exc

    def load(self):
        with self._lock:
            document = deepcopy(self._document)
        return self.document_to_memory(document)

    def transact(self, mutation):
        for _ in range(3):
            with self._lock:
                base = deepcopy(self._document)
            memory = self.document_to_memory(base)
            result = mutation(memory)
            updated = memory.to_document()
            if updated["content_digest"] == base["content_digest"]:
                return result
            with self._lock:
                if self._document["content_digest"] != base["content_digest"]:
                    continue
                self.__class__._document = deepcopy(updated)
                return result
        raise CausalMemoryError("fake durable causal memory changed during transaction")


def test_phase2_runtime_acceptance_uses_default_mission_surface_and_is_replay_safe(monkeypatch):
    FakeDurableCausalStore.reset()
    monkeypatch.setattr(acceptance, "SupabaseCausalMemory", FakeDurableCausalStore)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    clock = [datetime(2026, 9, 20, tzinfo=timezone.utc)]
    monkeypatch.setattr(acceptance, "_utc_now", lambda: clock[0])

    def fake_refresh(_army):
        return apply_causal_feedback(
            {"missions": [], "next_missions": [], "daily_lead_report": {}},
            loader=FakeDurableCausalStore().load,
            as_of=clock[0].isoformat(),
        )

    monkeypatch.setattr(acceptance, "refresh_director", fake_refresh)

    pending = acceptance.run_phase2_causal_runtime_acceptance()
    assert pending["ok"] is False
    assert pending["status"] == "WAIT_PROSPECTIVE_SYNTHETIC_EVALUATION"
    assert pending["scientific_forward_evidence"] is False
    assert pending["plan_durable"] is True
    assert pending["final_mission_count"] == 0
    assert FakeDurableCausalStore().load().events == {}

    clock[0] += timedelta(hours=21)
    first = acceptance.run_phase2_causal_runtime_acceptance()
    assert first["ok"] is True
    assert first["receipt_replay"] is False
    assert first["deployed_sha"] == "a" * 40
    assert first["support_consumed_by_default_director"] is True
    assert first["verified_independent_unit_count"] == acceptance.SUPPORT_PAIRS
    assert first["independent_unit_contract"] == "economic-realization-nonoverlap-v2"
    assert first["canonical_rejected_id_veto"] is True
    assert first["narrative_firewall"] is True
    assert first["stale_writer_replayed"] is True
    assert first["conflicting_replay_failed_closed"] is True
    assert first["simulated_outage_failed_closed"] is True
    assert first["corrupt_document_failed_closed"] is True
    assert first["decay_removed_missions"] is True
    assert first["contradiction_removed_missions"] is True
    assert first["support_confidence"] > first["post_contradiction_confidence"]
    assert first["final_mission_count"] == 0
    assert first["safety"]["trade_authority"] is False
    assert first["safety"]["promotion_authority"] is False
    assert first["safety"]["oos_opening_authority"] is False

    second = acceptance.run_phase2_causal_runtime_acceptance()
    assert second["ok"] is True
    assert second["receipt_replay"] is True
    assert second["canonical_rejected_id_veto"] is True
    assert second["verified_independent_unit_count"] == acceptance.SUPPORT_PAIRS
    assert second["independent_unit_contract"] == "economic-realization-nonoverlap-v2"
    assert second["final_mission_count"] == 0
    assert second["rejected_design_fingerprint"].startswith("mi-causal-v1:")
    assert second["rejected_effective_fingerprint"].startswith("mi-causal-pit-v1:")

    durable = FakeDurableCausalStore().load()
    hypothesis = durable.hypotheses[first["hypothesis_id"]]
    assert hypothesis.fingerprint in durable.rejected_fingerprints
    assert durable.effective_fingerprint(hypothesis) in durable.rejected_fingerprints
    assert durable.research_artifact(
        first["hypothesis_id"],
        lane="big_move",
        as_of="2099-01-01T00:00:00Z",
    ) is None

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import pytest

import money_intelligence_causal_acceptance as acceptance
import money_intelligence_causal_memory as causal_memory
from money_intelligence_causal_memory import CausalMemoryError, CausalRepricingMemory
from money_intelligence_mission_integration import apply_causal_feedback


@pytest.fixture(autouse=True)
def _test_only_attestation_key(monkeypatch):
    monkeypatch.setenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY", "ab" * 32)


def test_runtime_acceptance_rechecks_deployment_packaging_changes():
    workflow = Path(
        ".github/workflows/money-intelligence-causal-runtime-acceptance.yml"
    ).read_text(encoding="utf-8")

    assert "      - Dockerfile" in workflow
    assert "  schedule:" in workflow
    assert "Prospective guard passed; full synthetic runtime acceptance remains pending" in workflow


def test_runtime_acceptance_requires_immutable_base_image():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    first_instruction = next(
        line.strip() for line in dockerfile.splitlines() if line.strip()
    )

    assert first_instruction.startswith("FROM python:3.12-slim@sha256:")
    assert len(first_instruction.rsplit("@sha256:", 1)[1]) == 64


def test_fixture_subject_is_unique_for_each_full_deployed_sha():
    first = acceptance._ids("a" * 16 + "b" * 24)
    second = acceptance._ids("a" * 16 + "c" * 24)
    assert first["hypothesis"] != second["hypothesis"]
    assert acceptance._fixture_subject(first["hypothesis"]) != acceptance._fixture_subject(
        second["hypothesis"]
    )


def test_trusted_synthetic_pair_verifier_binds_future_fingerprint_namespace():
    ids = acceptance._ids("a" * 64)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    hypothesis = acceptance._contract(ids, base)
    contract = hypothesis.evaluation_pair_contracts[0]
    observed = base + timedelta(hours=1)
    available = observed + timedelta(hours=1, minutes=1)
    outcome = acceptance._observation(
        ids["support_outcome_1"], metric_name="matched_return", value=2.01,
        observed_at=observed, available_at=available, window_hours=1,
    )
    control = acceptance._observation(
        ids["support_control_1"], metric_name="matched_return", value=0.0,
        observed_at=observed, available_at=available, window_hours=1,
        selection_contract_id="phase2-runtime-exact-matched-control-v1",
    )
    verify = causal_memory._trusted_control_selection
    assert verify(hypothesis, contract, outcome, control)
    assert not verify(
        replace(hypothesis, statement="A real asset will outperform."),
        contract, outcome, control,
    )
    for changed in (
        replace(control, value=1.0),
        replace(control, venue="selected-after-outcome"),
        replace(control, revision_id="r2"),
    ):
        assert not verify(hypothesis, contract, outcome, changed)


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
            evaluation_pair_contracts=(),
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
    if prior_slots == 28:
        assert len(hypothesis.evaluation_units) > acceptance.SUPPORT_PAIRS
    assert verification["verified_p_value"] <= memory._project_threshold(hypothesis)


def test_synthetic_namespace_cannot_self_attest_support(monkeypatch):
    ids = acceptance._ids("c" * 40)
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    signed = CausalRepricingMemory()
    acceptance._seed_support(signed, ids, base)
    event = signed.events[ids["support"]]
    assert event.note.startswith("causal-acceptance-support-v1:")

    unsigned = CausalRepricingMemory()
    for item in signed.registration_log:
        if item["kind"] == "observation":
            unsigned.register_observation(signed.observations[item["id"]])
        elif item["kind"] == "hypothesis":
            unsigned.register_hypothesis(signed.hypotheses[item["id"]])
    with pytest.raises(CausalMemoryError, match="trusted writer attestation"):
        unsigned.record_evidence(replace(event, note=""))
    with pytest.raises(CausalMemoryError, match="trusted writer attestation"):
        unsigned.record_evidence(replace(event, note=event.note[:-1] + "0"))
    assert unsigned.record_evidence(event)

    document = signed.to_document()
    assert CausalRepricingMemory.from_document(document).events[ids["support"]].confirmatory
    monkeypatch.delenv("CAUSAL_ACCEPTANCE_ATTESTATION_KEY")
    restored = CausalRepricingMemory.from_document(document)
    assert restored.events[ids["support"]].confirmatory is False
    assert restored.confidence(ids["hypothesis"], as_of=event.evaluated_at).confirmatory_support_count == 0


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


def test_unrelated_redeploy_reuses_prospective_scientific_plan(monkeypatch):
    FakeDurableCausalStore.reset()
    monkeypatch.setattr(acceptance, "SupabaseCausalMemory", FakeDurableCausalStore)
    monkeypatch.setattr(acceptance, "_runtime_environment_identity", lambda: b"runtime-a")
    clock = datetime(2026, 9, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(acceptance, "_utc_now", lambda: clock)

    def fake_refresh(_army):
        return apply_causal_feedback(
            {"missions": [], "next_missions": [], "daily_lead_report": {}},
            loader=FakeDurableCausalStore().load,
            as_of=clock.isoformat(),
        )

    monkeypatch.setattr(acceptance, "refresh_director", fake_refresh)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    first = acceptance.run_phase2_causal_runtime_acceptance()
    frozen = FakeDurableCausalStore().load()
    assert first["status"] == "WAIT_PROSPECTIVE_SYNTHETIC_EVALUATION"
    assert len(frozen.hypotheses) == 1

    monkeypatch.setenv("RENDER_GIT_COMMIT", "b" * 40)
    second = acceptance.run_phase2_causal_runtime_acceptance()
    after_redeploy = FakeDurableCausalStore().load()
    assert second["deployed_sha"] == "b" * 40
    assert second["status"] == "WAIT_PROSPECTIVE_SYNTHETIC_EVALUATION"
    assert after_redeploy.hypotheses == frozen.hypotheses
    assert after_redeploy.hypothesis_order == frozen.hypothesis_order
    assert after_redeploy.events == {}


@pytest.mark.parametrize("changed_input", [
    "money_intelligence_causal_memory.py",
    "profitability_learning/runtime.py",
    "orchestration/rejected_fingerprints.json",
    "orchestration/trusted_executor_manifest.json",
    "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz",
    "requirements.txt",
    "Dockerfile",
])
def test_scientific_plan_namespace_tracks_packaged_inputs_not_state_docs(
    tmp_path, monkeypatch, changed_input
):
    monkeypatch.setattr(acceptance, "_runtime_environment_identity", lambda: b"runtime-a")
    inputs = (
        "money_intelligence_causal_memory.py",
        "profitability_learning/runtime.py",
        "orchestration/rejected_fingerprints.py",
        "orchestration/rejected_fingerprints.json",
        "orchestration/trusted_executor_manifest.json",
        "orchestration/signal_development_objective.json",
        "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz",
        "requirements.txt",
        "Dockerfile",
    )
    for relative in inputs:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    first = acceptance._scientific_plan_fingerprint(tmp_path)

    (tmp_path / "AI_STATE.md").write_text("unrelated state update", encoding="utf-8")
    assert acceptance._scientific_plan_fingerprint(tmp_path) == first
    (tmp_path / "profitability_learning" / "runtime.sqlite").write_text(
        "ephemeral local state", encoding="utf-8"
    )
    assert acceptance._scientific_plan_fingerprint(tmp_path) == first
    (tmp_path / changed_input).write_text("changed science input", encoding="utf-8")
    assert acceptance._scientific_plan_fingerprint(tmp_path) != first


def test_scientific_plan_namespace_tracks_resolved_runtime_identity(tmp_path, monkeypatch):
    inputs = (
        "money_intelligence_causal_memory.py",
        "requirements.txt",
        "Dockerfile",
        "orchestration/rejected_fingerprints.py",
        "orchestration/rejected_fingerprints.json",
        "orchestration/trusted_executor_manifest.json",
        "orchestration/signal_development_objective.json",
        "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz",
    )
    for relative in inputs:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(acceptance, "_runtime_environment_identity", lambda: b"dependency-a")
    first = acceptance._scientific_plan_fingerprint(tmp_path)
    monkeypatch.setattr(acceptance, "_runtime_environment_identity", lambda: b"dependency-b")
    assert acceptance._scientific_plan_fingerprint(tmp_path) != first


def test_runtime_identity_changes_with_resolved_distribution(tmp_path, monkeypatch):
    module = tmp_path / "scientific_dependency.py"
    module.write_text("VALUE = 'stable'\n", encoding="utf-8")

    class Distribution:
        metadata = {"Name": "scientific-dependency"}
        files = ("scientific_dependency.py",)

        def __init__(self, version, record):
            self.version = version
            self.record = record

        def read_text(self, name):
            assert name == "RECORD"
            return self.record

        @staticmethod
        def locate_file(relative):
            return tmp_path / relative

    installed = [Distribution("1.0", "original wheel")]
    monkeypatch.setattr(acceptance.metadata, "distributions", lambda: installed)
    first = acceptance._runtime_environment_identity()
    installed[0] = Distribution("2.0", "original wheel")
    assert acceptance._runtime_environment_identity() != first
    installed[0] = Distribution("1.0", "different wheel")
    assert acceptance._runtime_environment_identity() != first


def test_runtime_identity_changes_with_installed_distribution_contents(tmp_path, monkeypatch):
    module = tmp_path / "scientific_dependency.py"
    module.write_text("VALUE = 'original'\n", encoding="utf-8")

    class Distribution:
        metadata = {"Name": "scientific-dependency"}
        version = "1.0"
        files = ("scientific_dependency.py",)

        @staticmethod
        def read_text(name):
            assert name == "RECORD"
            return "scientific_dependency.py,sha256=unchanged-record,19"

        @staticmethod
        def locate_file(relative):
            return tmp_path / relative

    monkeypatch.setattr(acceptance.metadata, "distributions", lambda: [Distribution()])
    first = acceptance._runtime_environment_identity()
    module.write_text("VALUE = 'changed'\n", encoding="utf-8")
    assert acceptance._runtime_environment_identity() != first


def test_runtime_identity_ignores_generated_bytecode_cache_timestamps(tmp_path, monkeypatch):
    source_relative = acceptance.metadata.PackagePath("dependency/module.py")
    cache_relative = acceptance.metadata.PackagePath(
        "dependency/__pycache__/module.cpython-312.pyc"
    )
    source = tmp_path / source_relative
    cache = tmp_path / cache_relative
    source.parent.mkdir(parents=True, exist_ok=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("VALUE = 'stable'\n", encoding="utf-8")
    cache.write_bytes(b"timestamp-a:compiled-semantics")

    class Distribution:
        metadata = {"Name": "scientific-dependency"}
        version = "1.0"
        files = (source_relative, cache_relative)

        @staticmethod
        def read_text(name):
            assert name == "RECORD"
            return "dependency/module.py,sha256=source,17\n"

        @staticmethod
        def locate_file(relative):
            return tmp_path / relative

    monkeypatch.setattr(acceptance.metadata, "distributions", lambda: [Distribution()])
    first = acceptance._runtime_environment_identity()
    cache.write_bytes(b"timestamp-b:compiled-semantics")
    assert acceptance._runtime_environment_identity() == first
    source.write_text("VALUE = 'changed'\n", encoding="utf-8")
    assert acceptance._runtime_environment_identity() != first


def test_phase2_runtime_acceptance_uses_default_mission_surface_and_is_replay_safe(monkeypatch):
    FakeDurableCausalStore.reset()
    monkeypatch.setattr(acceptance, "SupabaseCausalMemory", FakeDurableCausalStore)
    monkeypatch.setattr(acceptance, "_runtime_environment_identity", lambda: b"runtime-a")
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

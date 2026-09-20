from copy import deepcopy
from threading import Lock

import money_intelligence_causal_acceptance as acceptance
from money_intelligence_causal_memory import CausalMemoryError, CausalRepricingMemory
from money_intelligence_mission_integration import apply_causal_feedback


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

    def fake_refresh(_army):
        return apply_causal_feedback(
            {"missions": [], "next_missions": [], "daily_lead_report": {}},
            loader=FakeDurableCausalStore().load,
        )

    monkeypatch.setattr(acceptance, "refresh_director", fake_refresh)

    first = acceptance.run_phase2_causal_runtime_acceptance()
    assert first["ok"] is True
    assert first["receipt_replay"] is False
    assert first["deployed_sha"] == "a" * 40
    assert first["support_consumed_by_default_director"] is True
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

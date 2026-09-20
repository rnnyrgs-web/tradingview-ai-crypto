"""Synthetic economic evidence must affect admission, not just displayed order."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from profitability_learning.contracts import SAFE, fingerprint
from profitability_learning.memory import Memory
from profitability_learning.runtime import (
    apply_queue_feedback, complete_experiment, enrich_legacy_lesson, refresh_director,
)
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from test_profitability_learning import experiment
from test_research_heavy_experiment_scheduler import _experiment


def configure(monkeypatch, tmp_path):
    path = tmp_path / "memory.sqlite"
    Memory(path)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(path))
    return path


def test_economic_learning_changes_actual_heavy_admission_after_restart(monkeypatch, tmp_path):
    path = configure(monkeypatch, tmp_path)
    old, fresh = _experiment("old-family", 100), _experiment("fresh-family", 90)
    old["family"] = "momentum"
    queue = {"experiments": [old, fresh]}
    assert build_heavy_dispatch_plan(apply_queue_feedback(queue))["selected"][0]["experiment_id"] == "old-family"
    completed = complete_experiment(experiment([-10, -10, -10]))
    # Re-open the persisted store and replay: no process-local vote or extra vote.
    assert Memory(path, create=False).snapshot()["experiments"][0]["experiment_id"] == completed["experiment_id"]
    complete_experiment(experiment([-10, -10, -10]))
    plan = build_heavy_dispatch_plan(apply_queue_feedback(queue))
    assert plan["selected"][0]["experiment_id"] == "fresh-family"
    assert len(Memory(path).snapshot()["experiments"]) == 1
    assert queue["experiments"][0] == old
    assert plan["heavy_slot_limit"] == 1


def test_legacy_missing_evidence_penalty_reaches_admission(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed",
                         "evidence_summary": {"experiment_id": "old"}})
    queue = {"experiments": [_experiment("old", 100), _experiment("new", 90)]}
    plan = build_heavy_dispatch_plan(apply_queue_feedback(queue))
    assert plan["selected"][0]["experiment_id"] == "new"


def test_rejected_fingerprint_is_ineligible_even_when_only_candidate(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    completed = complete_experiment(experiment([-10, -10, -10]))
    candidate = _experiment("rejected", 100)
    candidate["strategy_fingerprint"] = completed["contract"]["strategy_fingerprint"]
    queue = apply_queue_feedback({"experiments": [candidate]})
    assert build_heavy_dispatch_plan(queue)["selected"] == []
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True


@pytest.mark.parametrize("relabel", ["family", "mechanism", "economic_reason"])
def test_rejected_executable_semantics_cannot_reenter_by_relabeling(
    monkeypatch, tmp_path, relabel
):
    configure(monkeypatch, tmp_path)
    rejected = experiment([-10, -10, -10])
    complete_experiment(rejected)

    strategy = deepcopy(rejected["contract"]["strategy"])
    family = rejected["contract"]["family"]
    if relabel == "family":
        family = "renamed-family"
    elif relabel == "mechanism":
        strategy["mechanism"] = "rewritten mechanism prose"
    else:
        strategy["components"][0]["economic_reason"] = "rewritten narrative"
    candidate = _experiment(f"relabel-{relabel}", 100)
    candidate.update(
        family=family,
        strategy=strategy,
        strategy_fingerprint=fingerprint(strategy),
    )

    queue = apply_queue_feedback({"experiments": [candidate]})

    expected_reason = (
        "rejected_exact_fingerprint"
        if relabel == "family"
        else "rejected_semantic_identity"
    )
    assert queue["experiments"][0]["learning_feedback"]["reason"] == expected_reason
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_new_exact_fingerprint_without_verifiable_semantic_identity_fails_closed(
    monkeypatch, tmp_path
):
    configure(monkeypatch, tmp_path)
    candidate = _experiment("unverifiable-semantic", 100)
    candidate["strategy_fingerprint"] = "f" * 64

    queue = apply_queue_feedback({"experiments": [candidate]})

    assert queue["experiments"][0]["learning_feedback"]["reason"] == (
        "semantic_identity_unverifiable"
    )
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


@pytest.mark.parametrize("identity_fields", [(), ("strategy",)])
def test_missing_exact_identity_cannot_bypass_rejected_semantics(
    monkeypatch, tmp_path, identity_fields
):
    configure(monkeypatch, tmp_path)
    rejected = experiment([-10, -10, -10])
    complete_experiment(rejected)
    candidate = _experiment("identity-omission-relabel", 100)
    candidate["family"] = "renamed-family"
    candidate.pop("strategy_fingerprint")
    if "strategy" in identity_fields:
        candidate["strategy"] = deepcopy(rejected["contract"]["strategy"])
    else:
        candidate.pop("strategy")

    queue = apply_queue_feedback({"experiments": [candidate]})

    assert queue["experiments"][0]["learning_feedback"]["reason"] == (
        "semantic_identity_unverifiable"
    )
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_material_rule_change_has_distinct_semantic_identity(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    rejected = experiment([-10, -10, -10])
    complete_experiment(rejected)
    strategy = deepcopy(rejected["contract"]["strategy"])
    strategy["components"][0]["rule"] = "materially_distinct_inventory_rule"
    candidate = _experiment("material-rule-change", 100)
    candidate.update(
        family="new-hypothesis-family",
        strategy=strategy,
        strategy_fingerprint=fingerprint(strategy),
    )

    queue = apply_queue_feedback({"experiments": [candidate]})

    assert queue["experiments"][0]["learning_feedback"]["reason"] != (
        "rejected_semantic_identity"
    )
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is False
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 1


def test_director_cannot_offer_rejected_exact_fingerprint(monkeypatch, tmp_path):
    import research_director_runtime as director
    monkeypatch.setattr(director, "probe_bybit_oi_access", lambda: {"status": "source_error", "points_observed": 0})
    monkeypatch.setattr(director, "_STATE_PATH", tmp_path / "director.json")
    configure(monkeypatch, tmp_path)
    completed = complete_experiment(experiment([-10, -10, -10]))
    state = refresh_director({"workers": {"adaptive-accuracy": {
        "state": "resting", "latest_evidence": {"evidence_conclusion": "pending_validation",
        "experiment": {"experiment_id": "rejected", "hypothesis": "test rule",
                       "strategy_fingerprint": completed["contract"]["strategy_fingerprint"]}}}}})
    assert all(m.get("experiment_id") != "rejected" for m in state["next_missions"])
    assert all(m.get("experiment_id") != "rejected"
               for m in state["daily_lead_report"]["highest_priority_next_missions"])


def test_director_cannot_offer_candidate_with_missing_strategy_identity(
    monkeypatch, tmp_path
):
    import research_director_runtime as director
    monkeypatch.setattr(director, "probe_bybit_oi_access", lambda: {"status": "source_error", "points_observed": 0})
    monkeypatch.setattr(director, "_STATE_PATH", tmp_path / "director.json")
    configure(monkeypatch, tmp_path)
    state = refresh_director({"workers": {"adaptive-accuracy": {
        "state": "resting", "latest_evidence": {"evidence_conclusion": "pending_validation",
        "experiment": {"experiment_id": "missing-identity", "hypothesis": "test rule",
                       "family": "renamed-family"}}}}})
    assert all(m.get("experiment_id") != "missing-identity" for m in state["next_missions"])
    assert all(m.get("experiment_id") != "missing-identity"
               for m in state["daily_lead_report"]["highest_priority_next_missions"])


@pytest.mark.parametrize("factor", [True, "0.5", -1, 2, float("nan"), float("inf"), None])
def test_invalid_learning_factor_cannot_enter_heavy_admission(factor):
    candidate = _experiment("bad-feedback", 100)
    candidate["learning_feedback"] = {"factor": factor, "reason": "matched_family_economic_evidence",
                                      "changes_eligibility": False, **SAFE}
    assert build_heavy_dispatch_plan({"experiments": [candidate]})["selected"] == []


def test_learning_adjusts_economics_without_replacing_it_with_information_score(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed",
                         "evidence_summary": {"experiment_id": "old"}})
    old, fresh = _experiment("old", 100), _experiment("new", 40)
    fresh["information_priority"] = 999
    plan = build_heavy_dispatch_plan(apply_queue_feedback({"experiments": [old, fresh]}))
    assert plan["selected"][0]["experiment_id"] == "old"
    assert plan["selected"][0]["profitability_priority_score"] == pytest.approx(.5)
    assert plan["selected"][0]["base_profitability_priority_score"] == 1


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_memory_failure_never_dispatches_and_does_not_reset(monkeypatch, tmp_path, failure):
    path = configure(monkeypatch, tmp_path)
    complete_experiment(experiment())
    if failure == "missing":
        path.unlink()
    else:
        path.write_bytes(b"not a database")
    queue = apply_queue_feedback({"experiments": [_experiment("old", 100)]})
    assert queue["learning_status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert build_heavy_dispatch_plan(queue)["selected"] == []
    if failure == "missing":
        assert not path.exists()
    else:
        assert path.read_bytes() == b"not a database"


def test_real_factory_report_consumes_persistent_completion_feedback(monkeypatch, tmp_path):
    from research_experiment_factory_runner import build_factory_report
    import research_learning_state
    configure(monkeypatch, tmp_path)
    monkeypatch.setattr(research_learning_state, "DEFAULT_PATH", tmp_path / "legacy.json")
    rows = []
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i in range(40):
        t = start + timedelta(days=2 * i)
        rows.append({"forecast_at": t.isoformat(),
            "due_at": (t + timedelta(days=1)).isoformat(),
            "resolved_at": (t + timedelta(days=1, minutes=1)).isoformat(),
            "correct": i < 20, "horizon": "24h", "market_regime": "TREND",
            "direction": "LONG", "score": 85, "strategy_identity": "s1",
            "directional_return_pct": 1 if i < 20 else -1})
    first = build_factory_report(rows)["heavy_dispatch_plan"]["selected"][0]
    assert first["dimension"] == "score_band"
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed",
                         "evidence_summary": {"experiment_id": first["experiment_id"]}})
    report = build_factory_report(rows)
    assert report["heavy_dispatch_plan"]["selected"][0]["dimension"] == "direction"
    assert report["profitability_learning"]["missions"][0]["mode"] == "LEARN"
    assert report["automatic_execution_authority"] is False


@pytest.mark.parametrize("bad", [None, {}, {"factor": .5}, {"trade_authority": True},
                                  {"changes_eligibility": True}, {"reason": "unknown"},
                                  {"reason": []}, {"reason": {}}])
def test_malformed_or_unsafe_feedback_cannot_admit_work(bad):
    candidate = _experiment("unsafe", 100)
    feedback = {"factor": .5, "reason": "matched_family_economic_evidence",
                "changes_eligibility": False, **SAFE}
    if bad is None or bad == {} or bad == {"factor": .5}:
        feedback = bad
    else:
        feedback.update(bad)
    candidate["learning_feedback"] = feedback
    assert build_heavy_dispatch_plan({"experiments": [candidate]})["selected"] == []
    healthy = _experiment("healthy", 80)
    assert build_heavy_dispatch_plan({"experiments": [candidate, healthy]})["selected"][0]["experiment_id"] == "healthy"


def test_component_ablation_feedback_is_consumed_without_reopening_parent(monkeypatch, tmp_path):
    from profitability_learning.development import run_ablation
    from profitability_learning.contracts import fingerprint
    from test_profitability_learning_development import setup_ablation, evaluator
    configure(monkeypatch, tmp_path)
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    complete_experiment(full, ablation=ablation)
    harmful, useful = _experiment("a-harmful", 100), _experiment("z-useful", 100)
    for row, component in zip((harmful, useful), (2, 1)):
        row["family"] = "momentum"
        row["component_fingerprints"] = [fingerprint(e["contract"]["strategy"]["components"][component])]
    queue = apply_queue_feedback({"experiments": [harmful, useful]})
    plan = build_heavy_dispatch_plan(queue)
    assert plan["selected"][0]["experiment_id"] == "z-useful"
    assert plan["selected"][0]["profitability_priority_score"] == pytest.approx(1.15 / 1.3)
    assert build_heavy_dispatch_plan(apply_queue_feedback(queue))["selected"] == plan["selected"]


@pytest.mark.parametrize("split", ["CHRONOLOGICAL_VALIDATION", "RELEASED_OOS", "FORWARD"])
def test_protected_economics_do_not_tune_heavy_family_ranking(monkeypatch, tmp_path, split):
    configure(monkeypatch, tmp_path)
    evidence = experiment([-10, -10, -10], split=split)
    if split == "RELEASED_OOS":
        evidence["contract"]["release_ref"] = "fixture:independent-release"
    complete_experiment(evidence)
    candidate = _experiment("fresh-fingerprint", 100)
    candidate["family"] = "momentum"
    plan = build_heavy_dispatch_plan(apply_queue_feedback({"experiments": [candidate]}))
    assert plan["selected"][0]["profitability_priority_score"] == 1

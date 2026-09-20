"""Synthetic economic evidence must affect admission, not just displayed order."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from profitability_learning.contracts import SAFE, fingerprint
from profitability_learning.memory import Memory
from profitability_learning.runtime import (
    apply_queue_feedback, complete_experiment, enrich_legacy_lesson,
    factory_feedback, refresh_director,
)
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_quant_science_factory import (
    _scientific_design,
    _strategy_identity,
    verified_strategy_semantic_fingerprint,
)
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


def test_risk_blocked_positive_completion_rejects_exact_strategy_after_restart(
    monkeypatch, tmp_path
):
    path = configure(monkeypatch, tmp_path)
    source = _experiment("risk-blocked-positive", 100)
    source["family"] = "factory-restrictive-filter"
    passed = experiment([-5, -5, 30])
    passed["contract"]["strategy"] = deepcopy(source["strategy"])
    passed["contract"]["strategy_fingerprint"] = source["strategy_fingerprint"]
    passed["contract"]["family"] = source["family"]
    passed["status"] = "PASSED"
    passed["failure_reasons"] = []
    for trade in passed["trades"]:
        trade["asset"] = source["strategy"]["assets"][0]
        trade["timeframe"] = source["strategy"]["timeframe"]

    completed = complete_experiment(passed)
    restarted = Memory(path, create=False).snapshot()
    semantic = verified_strategy_semantic_fingerprint(source)
    candidate = deepcopy(source)
    candidate["experiment_id"] = "same-risk-after-restart"
    queue = apply_queue_feedback({"experiments": [candidate]})

    assert completed["outcome"] == "LEARN_AND_PIVOT"
    assert source["strategy_fingerprint"] in restarted["rejected_fingerprints"]
    assert semantic in restarted["rejected_semantic_fingerprints"]
    assert queue["experiments"][0]["learning_feedback"]["reason"] == (
        "rejected_exact_fingerprint"
    )
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 0


def test_historical_risk_flagged_success_rejects_exact_strategy_after_restart(
    monkeypatch, tmp_path
):
    path = configure(monkeypatch, tmp_path)
    source = _experiment("historical-risk-blocked-positive", 100)
    source["family"] = "factory-restrictive-filter"
    passed = experiment([-5, -5, 30])
    passed["contract"]["strategy"] = deepcopy(source["strategy"])
    passed["contract"]["strategy_fingerprint"] = source["strategy_fingerprint"]
    passed["contract"]["family"] = source["family"]
    passed["status"] = "PASSED"
    passed["failure_reasons"] = []
    for trade in passed["trades"]:
        trade["asset"] = source["strategy"]["assets"][0]
        trade["timeframe"] = source["strategy"]["timeframe"]
    complete_experiment(passed)
    archive = Memory(path, create=False).export()
    payload = archive["events"][0]["payload"]
    payload["outcome"] = "SUCCESS_LEARN"
    payload["next_research_question"] = (
        "Replicate the frozen economic mechanism independently; investigate "
        "return concentration."
    )
    archive["events"][0]["digest"] = fingerprint(payload)
    archive["sha256"] = fingerprint(archive["events"])
    historical_path = tmp_path / "historical.sqlite"
    Memory(historical_path).import_archive(archive)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(historical_path))

    restarted = Memory(historical_path, create=False).snapshot()
    semantic = verified_strategy_semantic_fingerprint(source)
    candidate = deepcopy(source)
    candidate["experiment_id"] = "same-historical-risk-after-restart"
    queue = apply_queue_feedback({"experiments": [candidate]})

    assert payload["source_status"] == "PASSED"
    assert "SINGLE_WINNER_DEPENDENCE" in payload["risk_flags"]
    assert source["strategy_fingerprint"] in restarted["rejected_fingerprints"]
    assert semantic in restarted["rejected_semantic_fingerprints"]
    assert queue["experiments"][0]["learning_feedback"]["reason"] == (
        "rejected_exact_fingerprint"
    )
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 0


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


def _completed_factory_strategy(candidate):
    rejected = experiment([-10, -10, -10])
    rejected["contract"]["strategy"] = deepcopy(candidate["strategy"])
    rejected["contract"]["strategy_fingerprint"] = candidate["strategy_fingerprint"]
    rejected["contract"]["family"] = candidate["family"]
    for trade in rejected["trades"]:
        trade["asset"] = candidate["strategy"]["assets"][0]
        trade["timeframe"] = candidate["strategy"]["timeframe"]
    return rejected


def _complete_positive_factory_strategy(candidate):
    passed = _completed_factory_strategy(candidate)
    passed["status"] = "PASSED"
    passed["failure_reasons"] = []
    return complete_experiment(passed)


def test_caller_declared_positive_completion_cannot_become_favorable_evidence(
    monkeypatch, tmp_path
):
    path = configure(monkeypatch, tmp_path)
    source = _experiment("caller-declared-positive", 100)
    source["family"] = "factory-restrictive-filter"

    completed = _complete_positive_factory_strategy(source)
    restarted = Memory(path, create=False).snapshot()
    semantic = verified_strategy_semantic_fingerprint(source)

    assert completed["favorable_evidence_provenance"] == (
        "UNVERIFIED_CALLER_RESULT"
    )
    assert restarted["families"][source["family"]]["promising_development"] == 0
    assert restarted["semantic_strategies"][semantic]["promising_development"] == 0
    assert not any(
        mission["mode"] == "EXPLOIT"
        for mission in factory_feedback()["missions"]
    )

    candidate = deepcopy(source)
    candidate["experiment_id"] = "same-behavior-after-restart"
    queue = apply_queue_feedback({"experiments": [candidate]})
    feedback = queue["experiments"][0]["learning_feedback"]

    assert feedback["factor"] == 1.0
    assert feedback["reason"] == "no_matched_completion"
    assert feedback["changes_eligibility"] is False
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 1


@pytest.mark.parametrize(
    "field",
    ["execution_rule", "component_rule", "component_parameters", "implementation_id"],
)
def test_cosmetic_rule_text_cannot_claim_new_semantics_with_same_executor(
    monkeypatch, tmp_path, field
):
    configure(monkeypatch, tmp_path)
    candidate = _experiment("same-executor-cosmetic-relabel", 100)
    candidate["family"] = "factory-restrictive-filter"
    candidate["science_design"] = _scientific_design(candidate)
    complete_experiment(_completed_factory_strategy(candidate))
    if field == "execution_rule":
        candidate["strategy"]["execution_rule"] = "cosmetically_renamed_executor"
    elif field == "component_rule":
        candidate["strategy"]["components"][0]["rule"] = "cosmetically_renamed_rule"
    elif field == "component_parameters":
        candidate["strategy"]["components"][0]["parameters"]["group"] = "RANGE"
    else:
        candidate["science_design"]["executor_implementation_id"] = "caller.asserted@v99"
    candidate["strategy_fingerprint"] = fingerprint(candidate["strategy"])

    assert build_heavy_dispatch_plan({"experiments": [candidate]})["selected"] == []

    queue = apply_queue_feedback({"experiments": [candidate]})

    assert queue["experiments"][0]["learning_feedback"]["reason"] in {
        "semantic_identity_unverifiable",
        "rejected_semantic_identity",
        "rejected_exact_fingerprint",
    }
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_trusted_behavior_change_has_distinct_semantic_identity(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    rejected_candidate = _experiment("rejected-regime", 100)
    rejected_candidate["family"] = "factory-restrictive-filter"
    rejected_candidate["science_design"] = _scientific_design(rejected_candidate)
    complete_experiment(_completed_factory_strategy(rejected_candidate))

    candidate = _experiment("different-direction-filter", 100)
    candidate.update(dimension="direction", group="LONG")
    candidate["science_design"] = _scientific_design(candidate)
    candidate["strategy"] = _strategy_identity(candidate, candidate["science_design"])
    candidate["strategy_fingerprint"] = fingerprint(candidate["strategy"])

    queue = apply_queue_feedback({"experiments": [candidate]})

    assert queue["experiments"][0]["learning_feedback"]["reason"] != (
        "rejected_semantic_identity"
    )
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is False
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("group", "RANGE"), ("target_horizon", "24h")],
)
def test_behavior_parameter_change_cannot_inherit_positive_semantic_evidence(
    monkeypatch, tmp_path, field, value
):
    configure(monkeypatch, tmp_path)
    source = _experiment("positive-trend-both", 100)
    source["family"] = "factory-restrictive-filter"
    _complete_positive_factory_strategy(source)

    candidate = _experiment("behaviorally-distinct", 100)
    candidate["family"] = "factory-restrictive-filter"
    candidate[field] = value
    candidate["science_design"] = _scientific_design(candidate)
    candidate["strategy"] = _strategy_identity(
        candidate, candidate["science_design"]
    )
    candidate["strategy_fingerprint"] = fingerprint(candidate["strategy"])

    queue = apply_queue_feedback({"experiments": [candidate]})
    feedback = queue["experiments"][0]["learning_feedback"]

    assert feedback["factor"] == 1.0
    assert feedback["reason"] != "matched_semantic_economic_evidence"
    assert feedback["changes_eligibility"] is False
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("group", "RANGE"), ("target_horizon", "24h")],
)
def test_behavior_parameter_change_is_not_over_vetoed_by_rejected_semantics(
    monkeypatch, tmp_path, field, value
):
    configure(monkeypatch, tmp_path)
    source = _experiment("rejected-trend-both", 100)
    source["family"] = "factory-restrictive-filter"
    complete_experiment(_completed_factory_strategy(source))

    candidate = _experiment("distinct-after-rejection", 100)
    candidate["family"] = "factory-restrictive-filter"
    candidate[field] = value
    candidate["science_design"] = _scientific_design(candidate)
    candidate["strategy"] = _strategy_identity(
        candidate, candidate["science_design"]
    )
    candidate["strategy_fingerprint"] = fingerprint(candidate["strategy"])

    assert (
        verified_strategy_semantic_fingerprint(source)
        != verified_strategy_semantic_fingerprint(candidate)
    )
    queue = apply_queue_feedback({"experiments": [candidate]})
    feedback = queue["experiments"][0]["learning_feedback"]
    assert feedback["reason"] != "rejected_semantic_identity"
    assert feedback["changes_eligibility"] is False
    assert build_heavy_dispatch_plan(queue)["selected_count"] == 1


def test_narrative_relabel_remains_semantically_identical():
    original = _experiment("narrative-original", 100)
    relabeled = deepcopy(original)
    relabeled["predicted_mechanism"] = "rewritten mechanism prose"
    relabeled["hypothesis"] = "rewritten economic story"
    relabeled["science_design"] = _scientific_design(relabeled)
    relabeled["strategy"] = _strategy_identity(
        relabeled, relabeled["science_design"]
    )
    relabeled["strategy_fingerprint"] = fingerprint(relabeled["strategy"])

    assert (
        verified_strategy_semantic_fingerprint(original)
        == verified_strategy_semantic_fingerprint(relabeled)
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda design: design["minimum_effect_to_continue"].update(
            precision_absolute_improvement=-1.0
        ),
        lambda design: design.update(minimum_evaluation_samples=1),
        lambda design: design.update(minimum_actionable_coverage=0.001),
        lambda design: design.update(minimum_evaluation_samples=True),
        lambda design: design.pop("minimum_actionable_coverage"),
        lambda design: design.update(caller_extension="weakened_gate"),
    ],
)
def test_caller_cannot_weaken_registered_validation_design(
    monkeypatch, tmp_path, mutation
):
    configure(monkeypatch, tmp_path)
    candidate = _experiment("forged-validation-gate", 100)
    mutation(candidate["science_design"])

    assert build_heavy_dispatch_plan({"experiments": [candidate]})["selected"] == []
    queue = apply_queue_feedback({"experiments": [candidate]})
    assert queue["experiments"][0]["learning_feedback"]["reason"] == (
        "semantic_identity_unverifiable"
    )
    assert queue["experiments"][0]["learning_feedback"]["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_known_positive_fingerprint_cannot_bypass_identity_with_omissions(
    monkeypatch, tmp_path
):
    configure(monkeypatch, tmp_path)
    source = _experiment("known-positive-source", 100)
    source["family"] = "factory-restrictive-filter"
    _complete_positive_factory_strategy(source)
    candidate = _experiment("known-positive-identity-omission", 100)
    candidate.pop("strategy")
    candidate.pop("science_design")
    candidate.update(dimension="direction", group="SELL")

    queue = apply_queue_feedback({"experiments": [candidate]})

    feedback = queue["experiments"][0]["learning_feedback"]
    assert feedback["factor"] == 0
    assert feedback["reason"] == "semantic_identity_unverifiable"
    assert feedback["changes_eligibility"] is True
    assert build_heavy_dispatch_plan(queue)["selected"] == []


def test_scheduler_rejects_asserted_positive_feedback_without_full_identity():
    candidate = _experiment("asserted-positive-identity-omission", 100)
    candidate.pop("strategy")
    candidate.pop("science_design")
    candidate.update(dimension="direction", group="SELL")
    candidate["learning_feedback"] = {
        "factor": 1.1,
        "reason": "matched_semantic_economic_evidence",
        "changes_eligibility": False,
        **SAFE,
    }

    assert build_heavy_dispatch_plan({"experiments": [candidate]})["selected"] == []


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


def test_director_cannot_offer_known_positive_fingerprint_with_changed_behavior(
    monkeypatch, tmp_path
):
    import research_director_runtime as director
    monkeypatch.setattr(director, "probe_bybit_oi_access", lambda: {"status": "source_error", "points_observed": 0})
    monkeypatch.setattr(director, "_STATE_PATH", tmp_path / "director.json")
    configure(monkeypatch, tmp_path)
    source = _experiment("known-positive-director-source", 100)
    source["family"] = "factory-restrictive-filter"
    _complete_positive_factory_strategy(source)
    state = refresh_director({"workers": {"adaptive-accuracy": {
        "state": "resting", "latest_evidence": {"evidence_conclusion": "pending_validation",
        "experiment": {
            "experiment_id": "known-positive-director-omission",
            "hypothesis": "changed behavior without trusted identity",
            "strategy_fingerprint": source["strategy_fingerprint"],
            "dimension": "direction",
            "group": "SELL",
        }}}}})

    assert all(m.get("experiment_id") != "known-positive-director-omission"
               for m in state["next_missions"])
    assert all(m.get("experiment_id") != "known-positive-director-omission"
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


def test_unverified_component_ablation_can_penalize_but_not_boost(monkeypatch, tmp_path):
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
    assert plan["selected"][0]["profitability_priority_score"] == pytest.approx(1 / 1.3)
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

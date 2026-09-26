from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3

import pytest

from test_profitability_learning import component, experiment
from test_profitability_learning_development import setup_ablation, evaluator
from profitability_learning.contracts import fingerprint, timestamp
from profitability_learning.development import run_ablation
from profitability_learning.memory import Memory
from profitability_learning.evolution import propose_successor, rank_candidates, learning_missions


def later(e, days=30):
    e = deepcopy(e)
    c = e["contract"]
    for name in ("start", "end", "frozen_at", "outcomes_observed_at"):
        c[name] = (timestamp(c[name]) + timedelta(days=days)).isoformat()
    for row in e["trades"]:
        for name in ("entry_at", "exit_at", "decision_at"):
            row[name] = (timestamp(row[name]) + timedelta(days=days)).isoformat()
        for f in row["features"].values():
            f["available_at"] = (timestamp(f["available_at"]) + timedelta(days=days)).isoformat()
    for row in e["equity"]:
        row["timestamp"] = (timestamp(row["timestamp"]) + timedelta(days=days)).isoformat()
    c["dataset_id"] += f"-{days}"
    c["dataset_sha256"] = fingerprint(c["dataset_id"])
    return e


def test_completion_is_immutable_idempotent_and_survives_restart(tmp_path):
    path = tmp_path / "learning.sqlite"
    m = Memory(path)
    e = experiment([-10, -10, -10])
    r = m.complete(e)
    assert r["outcome"] == "LEARN_AND_PIVOT"
    assert m.complete(e) == r
    snapshot = Memory(path).snapshot()
    assert len(snapshot["experiments"]) == 1
    assert e["contract"]["strategy_fingerprint"] in snapshot["rejected_fingerprints"]
    assert snapshot["families"]["momentum"]["independent_experiments"] == 1
    e["failure_reasons"] = ["rewritten outcome"]
    with pytest.raises(ValueError, match="immutable"):
        m.complete(e)


@pytest.mark.parametrize(
    ("pnls", "expected_flag"),
    [
        ([700, -500, -100], "CATASTROPHIC_LOSS"),
        ([-5, -5, 30], "SINGLE_WINNER_DEPENDENCE"),
    ],
)
def test_positive_tail_or_concentration_failure_is_not_success_learning(
    tmp_path, pnls, expected_flag
):
    e = experiment(pnls)
    e["status"] = "PASSED"
    e["failure_reasons"] = []

    completed = Memory(tmp_path / "memory.sqlite").complete(e)

    assert expected_flag in completed["risk_flags"]
    assert completed["metrics"]["net_pnl"] > 0
    assert completed["outcome"] == "LEARN_AND_PIVOT"


def test_positive_aggregated_event_tail_failure_is_not_success_learning(tmp_path):
    e = experiment([-150, -150, 100, 100, 100, 100])
    e["trades"][1]["event_id"] = e["trades"][0]["event_id"]
    e["status"] = "PASSED"
    e["failure_reasons"] = []

    completed = Memory(tmp_path / "memory.sqlite").complete(e)

    assert completed["metrics"]["worst_event_money"] == -300
    assert "CATASTROPHIC_LOSS" in completed["risk_flags"]
    assert completed["metrics"]["net_pnl"] > 0
    assert completed["outcome"] == "LEARN_AND_PIVOT"


def test_historical_risk_flagged_success_cannot_become_exploit_mission(tmp_path):
    e = experiment([-5, -5, 30])
    e["status"] = "PASSED"
    e["failure_reasons"] = []
    memory = Memory(tmp_path / "memory.sqlite")
    memory.complete(e)
    snapshot = memory.snapshot()
    record = snapshot["experiments"][0]
    # Exercise backward compatibility with an already-persisted favorable row.
    record["outcome"] = "SUCCESS_LEARN"
    record["favorable_evidence_provenance"] = "VERIFIED_EXECUTOR_BOUND_RESULT"

    mission = next(
        row
        for row in learning_missions(snapshot)
        if row["source_experiment_id"] == record["experiment_id"]
    )

    assert "SINGLE_WINNER_DEPENDENCE" in record["risk_flags"]
    assert mission["mode"] == "LEARN"
    assert mission["strategy_fingerprint"] is None


def test_underpowered_single_winner_diagnostic_does_not_reject_strategy(tmp_path):
    e = experiment([10])
    e["status"] = "PASSED"
    e["failure_reasons"] = []
    memory = Memory(tmp_path / "memory.sqlite")

    completed = memory.complete(e)
    snapshot = Memory(memory.path, create=False).snapshot()

    assert completed["outcome"] == "INCONCLUSIVE"
    assert completed["metrics"]["independent_event_count"] == 1
    assert "INSUFFICIENT_INDEPENDENT_EVENTS" in completed["risk_flags"]
    assert "SINGLE_WINNER_DEPENDENCE" in completed["risk_flags"]
    assert completed["contract"]["strategy_fingerprint"] not in (
        snapshot["rejected_fingerprints"]
    )
    assert not snapshot["rejected_semantic_fingerprints"]


def test_concurrent_replay_does_not_inflate_evidence(tmp_path):
    path = tmp_path / "memory.sqlite"
    Memory(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: Memory(path).complete(experiment()), range(8)))
    assert len(Memory(path).snapshot()["experiments"]) == 1


def test_overlapping_windows_are_not_independent_replications(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    m.complete(e)
    e["contract"]["dataset_id"] = "renamed-dataset"
    e["contract"]["dataset_sha256"] = "b" * 64
    m.complete(e)
    s = m.snapshot()
    assert s["families"]["momentum"]["independent_experiments"] == 1


def test_component_and_interaction_memory_keeps_ancestry(tmp_path):
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    m = Memory(tmp_path / "memory.sqlite")
    r = m.complete(full, ablation=ablation)
    s = m.snapshot()
    trend = fingerprint(e["contract"]["strategy"]["components"][1])
    assert s["components"][trend]["observations"][0]["effect"]["delta_compounded_return"] > 0
    assert s["components"][trend]["evidence_level"] != "PROVEN"
    assert len(s["interactions"]) == 1
    assert r["experiment_id"] in s["components"][trend]["strategies"][full["contract"]["strategy_fingerprint"]]


def test_infra_and_inconclusive_do_not_kill_mechanism(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment()
    e.update(status="INFRA_DATA_FAILURE", trades=[], equity=[], failure_reasons=["missing archive"])
    assert m.complete(e)["outcome"] == "INFRA_DATA_FAILURE"
    e = later(experiment([-1]), 30)
    assert m.complete(e)["outcome"] == "INCONCLUSIVE"
    assert not m.snapshot()["families"]["momentum"]["mechanism_dead"]


def test_mechanism_dead_needs_frozen_falsifier_and_independent_failures(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    e["contract"]["mechanism_falsifier"] = {"metric": "after_cost_expectancy_money", "maximum": 0,
                                             "minimum_independent_replications": 2}
    m.complete(e)
    result = m.complete(later(e))
    assert result["outcome"] == "MECHANISM_DEAD"
    assert m.snapshot()["families"]["momentum"]["mechanism_dead"]


def test_family_mechanism_and_economic_prose_cannot_reset_failure_memory(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    first = experiment([-10, -10, -10])
    first["contract"]["mechanism_falsifier"] = {
        "metric": "after_cost_expectancy_money",
        "maximum": 0,
        "minimum_independent_replications": 2,
    }
    m.complete(first)

    relabeled = later(first)
    relabeled["contract"]["family"] = "renamed-family"
    relabeled["contract"]["strategy"]["mechanism"] = "rewritten mechanism prose"
    relabeled["contract"]["strategy"]["components"][0]["economic_reason"] = (
        "Rewritten economic narrative with identical executable behavior."
    )
    relabeled["contract"]["strategy_fingerprint"] = fingerprint(
        relabeled["contract"]["strategy"]
    )

    result = m.complete(relabeled)
    snapshot = Memory(tmp_path / "memory.sqlite", create=False).snapshot()

    assert result["outcome"] == "MECHANISM_DEAD"
    assert len(snapshot["semantic_strategies"]) == 1
    semantic = next(iter(snapshot["semantic_strategies"].values()))
    assert semantic["development_failures"] == 2
    assert semantic["mechanism_dead"] is True
    assert semantic["families"] == ["momentum", "renamed-family"]
    assert semantic["semantic_fingerprint"] in snapshot["rejected_semantic_fingerprints"]


def successor_contract(parent):
    c = deepcopy(later(parent, 60)["contract"])
    c["strategy"]["components"].append(component("exit", "inventory_normalization"))
    c["strategy_fingerprint"] = fingerprint(c["strategy"])
    return c


def test_failure_can_generate_distinct_frozen_successor_and_preserve_rejection(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    r = m.complete(e)
    p = propose_successor(m.snapshot(), r["experiment_id"], successor_contract(e),
                          economic_reason="Fixed horizon may hold after inventory pressure dissipates.",
                          falsifier="After-cost return fails on fresh chronological replication.")
    assert p["strategy_fingerprint"] != e["contract"]["strategy_fingerprint"]
    assert r["experiment_id"] in p["ancestry"]["experiment_ids"]
    assert p["status"] == "FROZEN_RESEARCH_HYPOTHESIS_REQUIRES_REVIEW"
    assert p["automatic_execution_authority"] is False
    assert e["contract"]["strategy_fingerprint"] in m.snapshot()["rejected_fingerprints"]
    assert m.save_proposal(p) == p
    assert m.save_proposal(p) == p
    assert len(m.snapshot()["proposals"]) == 1


def test_parameter_tuning_and_cosmetic_relabel_are_not_material_successors(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    r = m.complete(e)
    c = later(e, 60)["contract"]
    c["strategy"]["components"][0]["parameters"]["window"] = 21
    c["strategy"]["mechanism"] = "a renamed mechanism"
    c["strategy_fingerprint"] = fingerprint(c["strategy"])
    with pytest.raises(ValueError, match="material"):
        propose_successor(m.snapshot(), r["experiment_id"], c, economic_reason="new", falsifier="negative")


def test_successor_requires_fresh_post_observation_chronology(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    r = m.complete(e)
    c = successor_contract(e)
    c["start"] = e["contract"]["start"]
    with pytest.raises(ValueError):
        propose_successor(m.snapshot(), r["experiment_id"], c, economic_reason="new exit", falsifier="negative")


def test_no_successor_can_be_mined_from_protected_validation_or_oos(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10], split="RELEASED_OOS")
    e["contract"]["release_ref"] = "independent:release"
    r = m.complete(e)
    with pytest.raises(ValueError, match="development"):
        propose_successor(m.snapshot(), r["experiment_id"], successor_contract(e), economic_reason="new", falsifier="negative")


def test_rank_uses_economic_memory_not_experiment_count(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    m.complete(e)
    base = {"base_priority": 1, "expected_economic_upside": .5, "information_gain": .7,
            "data_readiness": 1, "compute_cost": .2, "monetary_cost": 0, "time_to_result": .2}
    candidates = [{**base, "id": "loser", "family": "momentum"},
                  {**base, "id": "novel", "family": "other"}]
    result = rank_candidates(candidates, m.snapshot())
    assert result[0]["id"] == "novel"
    assert result[0]["mode"] == "EXPLORE"
    missions = learning_missions(m.snapshot())
    assert any(x["mode"] == "LEARN" for x in missions)
    assert all(x["automatic_execution_authority"] is False for x in missions)


def test_corrupt_store_does_not_reset_to_empty(tmp_path):
    path = tmp_path / "memory.sqlite"
    m = Memory(path)
    m.complete(experiment())
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE events SET payload = '{}' ")
    with pytest.raises(ValueError, match="integrity"):
        m.snapshot()


def test_export_import_preserves_component_and_trial_memory(tmp_path):
    m = Memory(tmp_path / "one.sqlite")
    m.complete(experiment())
    exported = m.export()
    n = Memory(tmp_path / "two.sqlite")
    n.import_archive(exported)
    n.import_archive(exported)
    assert n.snapshot() == m.snapshot()


def test_canonical_rejected_fingerprints_remain_in_memory(tmp_path):
    s = Memory(tmp_path / "memory.sqlite").snapshot()
    assert "DISC-LIQUIDITY-MEANREV-001-v1" in s["rejected_fingerprints"]
    assert "DISC-SQUEEZE-RETENTION-001-v1" not in s["rejected_fingerprints"]


def test_import_rejects_self_hashed_unsafe_schema(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment())
    archive = m.export()
    archive["events"][0]["payload"]["trade_authority"] = True
    archive["events"][0]["digest"] = fingerprint(archive["events"][0]["payload"])
    archive["sha256"] = fingerprint(archive["events"])
    n = Memory(tmp_path / "other.sqlite")
    with pytest.raises(ValueError, match="schema"):
        n.import_archive(archive)


def test_import_cannot_self_assert_verified_favorable_provenance(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment([10, 10, 10]))
    archive = m.export()
    archive["events"][0]["payload"]["favorable_evidence_provenance"] = (
        "VERIFIED_EXECUTOR_BOUND_RESULT"
    )
    archive["events"][0]["digest"] = fingerprint(
        archive["events"][0]["payload"]
    )
    archive["sha256"] = fingerprint(archive["events"])
    n = Memory(tmp_path / "other.sqlite")

    with pytest.raises(ValueError, match="schema"):
        n.import_archive(archive)


def test_same_semantic_successor_suppressed_across_fresh_windows(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e = experiment([-10, -10, -10])
    r = m.complete(e)
    p = propose_successor(m.snapshot(), r["experiment_id"], successor_contract(e), economic_reason="different exit", falsifier="negative")
    m.save_proposal(p)
    c = successor_contract(later(e, 30))
    p2 = propose_successor(m.snapshot(), r["experiment_id"], c, economic_reason="different exit", falsifier="negative")
    with pytest.raises(ValueError, match="duplicate"):
        m.save_proposal(p2)


def test_component_evidence_changes_priority_and_replay_cannot_amplify_it(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    m.complete(full, ablation=ablation)
    good, bad = e["contract"]["ablation_components"]
    ranked = rank_candidates([{"id": "good", "family": "new", "component_fingerprints": [good]},
                              {"id": "bad", "family": "new", "component_fingerprints": [bad]}], m.snapshot())
    assert ranked[0]["id"] == "good"
    assert ranked[0]["learning_priority"] > ranked[1]["learning_priority"]


def test_repeat_component_findings_do_not_duplicate_successor_queue(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    m.complete(full, ablation=ablation)
    snapshot = m.snapshot()
    snapshot["experiments"].append(deepcopy(snapshot["experiments"][0]))
    missions = learning_missions(snapshot)
    assert len({row["id"] for row in missions}) == len(missions)


def test_overlapping_component_relabels_cannot_change_priority_vote(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    m.complete(full, ablation=ablation)
    trend = e["contract"]["ablation_components"][0]
    def negative(strategy, data):
        out = experiment([-10 if any(c["kind"] == "trend_filter" for c in strategy["components"]) else 10] * 3)
        return {k: out[k] for k in ("status", "trades", "equity", "failure_reasons")}
    for day in (30, 60):
        shifted = later(e, day)
        dataset = deepcopy(data)
        dataset["start"], dataset["end"] = shifted["contract"]["start"], shifted["contract"]["end"]
        for row in dataset["rows"]:
            for k in ("timestamp", "available_at"):
                row[k] = (timestamp(row[k]) + timedelta(days=day)).isoformat()
        shifted["contract"]["dataset_sha256"] = fingerprint(dataset)
        def shifted_evaluator(strategy, data, day=day):
            raw = negative(strategy, data)
            return {k: later({**raw, "contract": e["contract"]}, day)[k] for k in raw}
        a = run_ablation(shifted["contract"], dataset, shifted_evaluator)
        f = deepcopy(a["variants"][0]["experiment"])
        f["contract"] = shifted["contract"]
        m.complete(f, ablation=a)
    candidate = [{"id": "test", "family": "new", "component_fingerprints": [trend]}]
    before = rank_candidates(candidate, m.snapshot())[0]["component_factor"]
    for i in range(4):
        duplicate, a = deepcopy(full), deepcopy(ablation)
        duplicate["contract"]["provenance_ref"] = f"relabel:{i}"
        a["contract"]["provenance_ref"] = f"relabel:{i}"
        for v in a["variants"]:
            v["experiment"]["contract"]["provenance_ref"] = f"relabel:{i}"
        m.complete(duplicate, ablation=a)
    assert rank_candidates(candidate, m.snapshot())[0]["component_factor"] == before


def test_protected_windows_cannot_erase_development_failures(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment([-10] * 4))
    before = m.snapshot()["families"]["momentum"]["development_failures"]
    e = experiment([-10] * 3, split="RELEASED_OOS")
    e["contract"]["release_ref"] = "independent:release"
    m.complete(e)
    assert m.snapshot()["families"]["momentum"]["development_failures"] == before == 1


def test_rejected_exact_strategy_never_becomes_exploit_mission(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment([-10] * 3))
    e = later(experiment([10] * 3), 30)
    e["status"] = "PASSED"
    m.complete(e)
    s = m.snapshot()
    assert s["families"]["momentum"]["promising_development"] == 0
    assert not any(r["mode"] == "EXPLOIT" and r["learning_priority"] > 0 for r in learning_missions(s))


def test_rejected_semantic_relabel_never_becomes_exploit_mission(tmp_path):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment([-10] * 3))
    relabeled = later(experiment([10] * 3), 30)
    relabeled["status"] = "PASSED"
    relabeled["contract"]["family"] = "renamed-family"
    relabeled["contract"]["strategy"]["mechanism"] = "renamed mechanism"
    relabeled["contract"]["strategy"]["components"][0]["economic_reason"] = (
        "renamed economic prose"
    )
    relabeled["contract"]["strategy_fingerprint"] = fingerprint(
        relabeled["contract"]["strategy"]
    )
    m.complete(relabeled)

    snapshot = m.snapshot()
    semantic = next(iter(snapshot["semantic_strategies"].values()))

    assert semantic["promising_development"] == 0
    assert not any(
        row["mode"] == "EXPLOIT" and row["learning_priority"] > 0
        for row in learning_missions(snapshot)
    )


@pytest.mark.parametrize("field", ["source_status", "risk_flags", "attribution", "interaction_evidence", "input_digest"])
def test_incomplete_archive_rejected_before_commit(tmp_path, field):
    m = Memory(tmp_path / "memory.sqlite")
    m.complete(experiment())
    archive = m.export()
    del archive["events"][0]["payload"][field]
    archive["events"][0]["digest"] = fingerprint(archive["events"][0]["payload"])
    archive["sha256"] = fingerprint(archive["events"])
    n = Memory(tmp_path / "other.sqlite")
    with pytest.raises(ValueError, match="schema"):
        n.import_archive(archive)
    assert not n.snapshot()["experiments"]

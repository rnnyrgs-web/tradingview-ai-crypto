from copy import deepcopy
import json

import pytest

from test_profitability_learning import experiment
from test_profitability_learning_development import setup_ablation, evaluator
from test_research_heavy_experiment_scheduler import _experiment
from profitability_learning.development import run_ablation
from profitability_learning.memory import Memory
from profitability_learning.runtime import (complete_experiment, learning_snapshot,
    enrich_legacy_lesson, factory_feedback, refresh_director)


def configure(monkeypatch, tmp_path):
    path = tmp_path / "durable.sqlite"
    Memory(path)
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(path))
    return path


def test_completion_to_persistence_to_director_mission(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    e = experiment([-10, -10, -10])
    result = complete_experiment(e)
    assert result["outcome"] == "LEARN_AND_PIVOT"
    feedback = factory_feedback()
    assert feedback["status"] == "AVAILABLE"
    assert len(feedback["missions"]) == 1
    assert feedback["missions"][0]["source_experiment_id"] == result["experiment_id"]
    state = refresh_director({"workers": {}})
    assert any(m["lane"] == "profitability-learning" for m in state["missions"])
    assert state["profitability_learning"]["progress_metric"] == "credible_economic_evidence_or_uncertainty_reduction"
    assert state["trade_authority"] is False


def test_useful_and_harmful_components_generate_actual_successor_specs(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    e, data = setup_ablation()
    ablation = run_ablation(e["contract"], data, evaluator)
    full = deepcopy(ablation["variants"][0]["experiment"])
    full["contract"] = e["contract"]
    r = complete_experiment(full, ablation=ablation)
    successors = r["successor_hypotheses"]
    assert successors
    assert any(p["kind"] == "COMPONENT_REPLACEMENT" for p in successors)
    proposal = next(p for p in successors if p["kind"] == "COMPONENT_REPLACEMENT")
    assert proposal["strategy_fingerprint"] != e["contract"]["strategy_fingerprint"]
    assert proposal["ancestry"]["experiment_id"] == r["experiment_id"]
    assert proposal["status"] == "BLOCKED_FRESH_CONTRACT_REQUIRED"
    assert all(c["kind"] != "exit" for c in proposal["strategy"]["components"])


def test_unconfigured_memory_is_explicit_and_never_claims_durability(monkeypatch):
    monkeypatch.delenv("PROFITABILITY_LEARNING_DB", raising=False)
    r = complete_experiment(experiment())
    assert r["persistence_status"] == "WAIT_MEMORY_NOT_CONFIGURED"
    assert learning_snapshot()["status"] == "WAIT_MEMORY_NOT_CONFIGURED"


def test_configured_missing_or_corrupt_store_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(tmp_path / "absent.sqlite"))
    with pytest.raises(ValueError, match="missing"):
        complete_experiment(experiment())
    assert factory_feedback()["status"] == "WAIT_MEMORY_UNAVAILABLE"
    assert factory_feedback()["missions"] == []


def test_legacy_completion_gets_durable_classification_without_fake_metrics(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    from research_learning_state import append_lesson, load_state
    path = tmp_path / "legacy.json"
    append_lesson({"fingerprint": "old-fp", "hypothesis": "a hypothesis", "outcome": "validation_failed"}, path)
    saved = load_state(path)["lessons"][0]
    learning = saved["evidence_summary"]["profitability_learning"]
    assert learning["outcome"] == "INCONCLUSIVE"
    assert learning["economic_metrics_available"] is False
    assert len(learning_snapshot()["memory"]["legacy_outcomes"]) == 1


def test_factory_runner_includes_learning_missions(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    complete_experiment(experiment([-10, -10, -10]))
    from research_experiment_factory_runner import build_factory_report
    r = build_factory_report([])
    assert r["profitability_learning"]["missions"]
    assert r["automatic_execution_authority"] is False


def test_runtime_rejects_legacy_summary_overwrite(monkeypatch):
    monkeypatch.delenv("PROFITABILITY_LEARNING_DB", raising=False)
    lesson = {"fingerprint": "x", "outcome": "rejected", "evidence_summary": {"old": 12}}
    r = enrich_legacy_lesson(lesson)
    assert r["evidence_summary"]["old"] == 12
    assert "profitability_learning" not in lesson["evidence_summary"]


def test_cli_completion_and_archive_roundtrip(monkeypatch, tmp_path, capsys):
    from profitability_learning.__main__ import main
    source = tmp_path / "experiment.json"
    source.write_text(json.dumps(experiment()))
    database = tmp_path / "memory.sqlite"
    assert main(["--db", str(database), "init"]) == 0
    assert main(["--db", str(database), "complete", str(source)]) == 0
    archive = tmp_path / "archive.json"
    assert main(["--db", str(database), "export", str(archive)]) == 0
    assert json.loads(archive.read_text())["events"]


def test_existing_legacy_completion_generates_missing_evidence_mission(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed", "hypothesis": "test a rule",
                         "evidence_summary": {"experiment_id": "existing-exp"}})
    feedback = factory_feedback()
    assert any(m["source_experiment_id"] == "existing-exp" and m["mode"] == "LEARN" for m in feedback["missions"])


def test_existing_director_ranking_receives_memory_feedback(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    identity = _experiment("existing-exp", 100)
    army = {"workers": {"adaptive-accuracy": {"state": "resting", "latest_evidence": {
        "evidence_conclusion": "pending_validation", "experiment": identity}}}}
    before = refresh_director(army)["missions"][0]["priority"]
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed", "hypothesis": "test a rule",
                         "evidence_summary": {"experiment_id": "existing-exp"}})
    after = next(m for m in refresh_director(army)["missions"] if m["lane"] == "adaptive-accuracy")
    assert after["priority"] < before
    assert after["learning_feedback"]["reason"] == "prior_completion_requires_new_evidence"


def test_existing_factory_candidates_reordered_from_completed_memory(monkeypatch, tmp_path):
    from profitability_learning.runtime import apply_queue_feedback
    configure(monkeypatch, tmp_path)
    enrich_legacy_lesson({"fingerprint": "legacy", "outcome": "validation_failed", "hypothesis": "test a rule",
                         "evidence_summary": {"experiment_id": "old"}})
    old, fresh = _experiment("old", 100), _experiment("fresh", 90)
    old["information_priority"], fresh["information_priority"] = 1.0, .9
    queue = {"experiments": [old, fresh]}
    result = apply_queue_feedback(queue)
    assert result["experiments"][0]["experiment_id"] == "fresh"
    assert queue["experiments"][0]["experiment_id"] == "old"


def test_configured_memory_outage_blocks_new_candidate_dispatch(monkeypatch, tmp_path):
    from profitability_learning.runtime import apply_queue_feedback
    monkeypatch.setenv("PROFITABILITY_LEARNING_DB", str(tmp_path / "absent.sqlite"))
    result = apply_queue_feedback({"experiments": [{"experiment_id": "x", "information_priority": 1}], "experiment_count": 1})
    assert result["experiments"] == []
    assert result["experiment_count"] == 0
    assert result["learning_status"] == "WAIT_MEMORY_UNAVAILABLE"
    state = refresh_director({"workers": {"learning-diagnostics": {"state": "resting"}}})
    assert state["next_missions"] == []

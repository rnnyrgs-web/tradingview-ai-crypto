import json
from pathlib import Path


def test_accuracy_profitability_roadmap_is_explicitly_profitability_first():
    roadmap = json.loads(Path("orchestration/accuracy_profitability_roadmap.json").read_text(encoding="utf-8"))
    objective = roadmap["objective"].lower()
    assert "profitability" in objective
    assert "first" in objective
    assert objective.index("profitability") < objective.index("accuracy")


def test_rejected_profitability_candidate_is_not_rescheduled_as_always_on_worker():
    import continuous_worker_army as army

    names = {worker.name for worker in army.WORKERS}
    scripts = {worker.script for worker in army.WORKERS}
    assert "basis-falsification-btc" not in names
    assert "basis_falsification_runner.py" not in scripts

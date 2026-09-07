import json

from research_aggregation import aggregate_registry_artifacts
from research_artifact import seal_research_payload


def _write(path, generated_at, digest_marker, passed=True):
    payload = {
        "generated_at": generated_at,
        "eligible_strategies": [{
            "symbol": "ETH-USDT",
            "bar": "1H",
            "strategy_family": "trend",
            "validation": {"trades": 10},
            "holdout_test": {"trades": 10},
            "robustness": {"passed": passed, "marker": digest_marker},
        }],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seal_research_payload(payload)), encoding="utf-8")


def test_aggregator_requires_three_distinct_sealed_robust_runs(tmp_path):
    for index in range(3):
        _write(tmp_path / str(index) / "strategy_registry.json", f"t{index}", index)
    result = aggregate_registry_artifacts(tmp_path)
    assert result["valid_artifact_count"] == 3
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["distinct_sealed_runs"] == 3
    assert result["candidates"][0]["live_approved"] is False


def test_aggregator_rejects_tampering_and_nonrobust_results(tmp_path):
    _write(tmp_path / "good" / "strategy_registry.json", "t1", 1, passed=False)
    _write(tmp_path / "bad" / "strategy_registry.json", "t2", 2)
    path = tmp_path / "bad" / "strategy_registry.json"
    envelope = json.loads(path.read_text())
    envelope["payload"]["eligible_strategies"][0]["symbol"] = "ALTERED"
    path.write_text(json.dumps(envelope))
    result = aggregate_registry_artifacts(tmp_path)
    assert result["candidate_count"] == 0
    assert len(result["invalid_artifacts"]) == 1

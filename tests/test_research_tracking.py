import sys
import types

from research_tracking import log_experiment


def run_payload():
    return {
        "experiment_id": "EXP-001",
        "hypothesis_id": "H-001",
        "strategy_fingerprint": "fingerprint-001",
        "git_sha": "abc123",
        "dataset_sha256": "data123",
        "parameters": {"lookback": 24},
        "metrics": {"net_expectancy_pct": 0.2, "profit_factor": 1.3},
        "state": "VALIDATION_PASS",
        "rejection_reason": None,
    }


def test_tracking_is_disabled_without_uri_and_does_not_require_mlflow(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delitem(sys.modules, "mlflow", raising=False)
    result = log_experiment(run_payload())
    assert result["status"] == "TRACKING_DISABLED"
    assert result["logged"] is False


def test_tracking_logs_identity_parameters_and_metrics(monkeypatch):
    calls = {"params": None, "metrics": None, "tags": {}}

    class RunContext:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    fake = types.SimpleNamespace(
        set_tracking_uri=lambda uri: calls.update(uri=uri),
        set_experiment=lambda name: calls.update(experiment=name),
        start_run=lambda run_name=None: RunContext(),
        log_params=lambda value: calls.update(params=value),
        log_metrics=lambda value: calls.update(metrics=value),
        set_tags=lambda value: calls["tags"].update(value),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake)
    result = log_experiment(run_payload(), tracking_uri="file:///tmp/mlruns")
    assert result["status"] == "LOGGED"
    assert calls["params"] == {"lookback": 24}
    assert calls["metrics"]["net_expectancy_pct"] == 0.2
    assert calls["tags"]["strategy_fingerprint"] == "fingerprint-001"
    assert calls["tags"]["dataset_sha256"] == "data123"

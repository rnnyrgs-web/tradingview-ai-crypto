"""Optional experiment tracking for deterministic research runs.

This module deliberately imports MLflow lazily so production web/runtime paths do
not gain a heavyweight dependency. Tracking failure never becomes evidence of a
successful research run.
"""

from __future__ import annotations

import importlib
from math import isfinite
import os
from typing import Any


def _primitive_params(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    result = {}
    for key, value in values.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            result[str(key)] = value
        else:
            result[str(key)] = repr(value)
    return result


def _numeric_metrics(values: Any) -> dict[str, float]:
    if not isinstance(values, dict):
        return {}
    result = {}
    for key, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(number):
            result[str(key)] = number
    return result


def log_experiment(run: dict, *, tracking_uri: str | None = None) -> dict:
    uri = str(tracking_uri or os.getenv("MLFLOW_TRACKING_URI") or "").strip()
    if not uri:
        return {"status": "TRACKING_DISABLED", "logged": False}
    if not isinstance(run, dict):
        return {"status": "TRACKING_FAILED", "logged": False, "reason": "run_not_object"}

    try:
        mlflow = importlib.import_module("mlflow")
    except (ImportError, ModuleNotFoundError):
        return {"status": "TRACKING_UNAVAILABLE", "logged": False}

    experiment_id = str(run.get("experiment_id") or "").strip()
    try:
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(str(run.get("experiment_name") or "one-verified-edge"))
        with mlflow.start_run(run_name=experiment_id or None):
            mlflow.log_params(_primitive_params(run.get("parameters")))
            mlflow.log_metrics(_numeric_metrics(run.get("metrics")))
            tags = {
                "experiment_id": experiment_id,
                "hypothesis_id": str(run.get("hypothesis_id") or ""),
                "strategy_fingerprint": str(run.get("strategy_fingerprint") or ""),
                "git_sha": str(run.get("git_sha") or ""),
                "dataset_sha256": str(run.get("dataset_sha256") or ""),
                "state": str(run.get("state") or ""),
                "rejection_reason": str(run.get("rejection_reason") or ""),
            }
            mlflow.set_tags(tags)
    except Exception as exc:  # MLflow backends may fail independently of research execution.
        return {
            "status": "TRACKING_FAILED",
            "logged": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }
    return {"status": "LOGGED", "logged": True, "experiment_id": experiment_id}

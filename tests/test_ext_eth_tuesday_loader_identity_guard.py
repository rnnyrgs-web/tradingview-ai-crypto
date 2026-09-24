from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
PROVENANCE = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution_provenance.json"
)
FINAL_RUNNER = (
    ROOT
    / "orchestration/external_replication/eth_tuesday_drift_stage1_frozen_runner.py"
)
EXPECTED_PROVENANCE_SHA256 = "4499df212a3fef33ef3382b42f8cac552f95595c79f92f9cfbd72ccb3d7c4bc9"
EXPECTED_RISK_AMENDMENT_SHA256 = "8e13286cd6c586c98f6ade79409a243efde266b55e7f4ee57492affd97c4c2c0"
EXPECTED_RISK_RUNNER_BLOB = "f39e0b03064036fd7cb66174d744ec789ecd6e28"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def test_final_stage1_binds_one_isolated_protected_safe_loader_without_rewriting_prior_artifacts():
    """Executable GREEN contract for the frozen execution-provenance blocker.

    The original risk amendment is append-only and keeps its original digest/runner
    binding. A new provenance artifact therefore binds a final authority wrapper plus
    one stdlib-only protected-safe loader. The final wrapper supplies development-only
    rows to the already-frozen risk evaluator instead of invoking its unsafe canonical
    loader entry.
    """
    binding = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    supplied = binding.pop("artifact_sha256")
    assert supplied == EXPECTED_PROVENANCE_SHA256
    assert hashlib.sha256(_canonical_json(binding)).hexdigest() == supplied
    binding["artifact_sha256"] = supplied

    assert binding["risk_amendment_sha256"] == EXPECTED_RISK_AMENDMENT_SHA256
    assert binding["risk_guarded_runner"]["git_blob_sha1"] == EXPECTED_RISK_RUNNER_BLOB
    assert binding["scientific_reason"]["prior_artifacts_mutated"] is False
    assert binding["formed_pre_outcome"] is True
    assert binding["outcomes_read_to_form_binding"] is False
    assert all(value is False for value in binding["authority_locks"].values())

    loader_binding = binding["protected_safe_loader"]
    loader_path = ROOT / loader_binding["path"]
    loader_source = loader_path.read_bytes()
    assert _git_blob_sha1(loader_source) == loader_binding["git_blob_sha1"]
    assert loader_binding["dependency_policy"] == "STDLIB_ONLY_NO_PROJECT_MODULE_IMPORTS"
    assert loader_binding["protected_tail_policy"] == "TIMESTAMP_ONLY_NO_OHLCV_JSON_DECODE"

    source_text = loader_source.decode("utf-8")
    forbidden_imports = (
        "strategy_dataset_preflight",
        "btc_leadlag_selection",
        "liquidity_mean_reversion_selection",
        "profitability_learning",
        "volatility_breakout_selection",
    )
    assert not any(name in source_text for name in forbidden_imports)

    final_binding = binding["final_stage1_runner"]
    final_source = FINAL_RUNNER.read_bytes()
    assert _git_blob_sha1(final_source) == final_binding["git_blob_sha1"]
    final_text = final_source.decode("utf-8")
    assert "base.load_frozen_eth_rows()" not in final_text
    assert "risk_guard.run_canonical_stage1_guarded()" not in final_text
    assert "protected_loader.load_frozen_eth_development_rows()" in final_text
    assert "risk_guard.evaluate_stage1_guarded(rows)" in final_text


def test_final_runner_runtime_validates_all_behavior_bearing_file_identities():
    from orchestration.external_replication import eth_tuesday_drift_stage1_frozen_runner as final

    binding = final.load_and_validate_execution_provenance()
    assert binding["artifact_sha256"] == EXPECTED_PROVENANCE_SHA256
    assert binding["protected_safe_loader"]["git_blob_sha1"] == "791358a1a48993e3ffbbee42c8a561313d8f60ae"
    assert binding["final_stage1_runner"]["git_blob_sha1"] == "f8440fbf543e6d534cd497b4dd9d251055679784"


def test_bound_loader_materializes_only_frozen_development_eth_rows():
    """Exercise the actual bound loader without computing any strategy outcome."""
    from orchestration.external_replication import eth_tuesday_protected_safe_loader as loader

    rows = loader.load_frozen_eth_development_rows()
    assert rows
    protected_ms = int(loader._parse_hour(loader.PROTECTED_START_UTC).timestamp() * 1000)
    cutoff_ms = int(loader._parse_hour(loader.DEVELOPMENT_END_UTC).timestamp() * 1000)
    assert int(rows[-1]["ts"]) == cutoff_ms
    assert all(int(row["ts"]) < protected_ms for row in rows)
    assert all(float(row["open"]) > 0 for row in rows)

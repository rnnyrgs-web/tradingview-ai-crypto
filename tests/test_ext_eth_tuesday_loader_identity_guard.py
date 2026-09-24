from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
RISK_AMENDMENT = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_risk_amendment.json"
)
GUARDED_RUNNER = (
    ROOT
    / "orchestration/external_replication/eth_tuesday_drift_stage1_guarded_runner.py"
)


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def test_guarded_stage1_must_bind_one_isolated_protected_safe_loader():
    """Executable falsifier for the frozen execution-provenance blocker.

    The current base runner dynamically imports strategy_dataset_preflight.py, whose
    import-time/validation closure reaches additional mutable modules. Binding only
    the base runner therefore does not freeze the code that decides whether protected
    OHLCV stays opaque. The bounded successor is one isolated stdlib-only loader whose
    complete file identity is recorded in the pre-outcome risk amendment and invoked
    by the only authority-bearing guarded Stage-1 path.
    """
    amendment = json.loads(RISK_AMENDMENT.read_text(encoding="utf-8"))
    binding = amendment.get("protected_safe_loader")
    assert isinstance(binding, dict), (
        "Stage-1 risk amendment must bind an isolated protected-safe loader before "
        "real evidence authority"
    )

    relative_path = binding.get("path")
    expected_blob = binding.get("git_blob_sha1")
    assert isinstance(relative_path, str) and relative_path
    assert isinstance(expected_blob, str) and len(expected_blob) == 40

    loader_path = ROOT / relative_path
    assert loader_path.is_file(), "bound protected-safe loader path is missing"
    loader_source = loader_path.read_bytes()
    assert _git_blob_sha1(loader_source) == expected_blob, (
        "protected-safe loader bytes drifted from the frozen risk amendment"
    )

    # Keep the isolated loader's dependency surface auditable and deterministic.
    source_text = loader_source.decode("utf-8")
    forbidden_imports = (
        "strategy_dataset_preflight",
        "btc_leadlag_selection",
        "liquidity_mean_reversion_selection",
        "profitability_learning",
        "volatility_breakout_selection",
    )
    assert not any(name in source_text for name in forbidden_imports), (
        "protected-safe loader must not re-open the mutable behavior-bearing closure"
    )

    guarded_source = GUARDED_RUNNER.read_text(encoding="utf-8")
    assert "base.load_frozen_eth_rows()" not in guarded_source, (
        "authority-bearing guarded Stage-1 path still uses the unbound dynamic loader"
    )
    assert Path(relative_path).stem in guarded_source, (
        "guarded Stage-1 path does not invoke the loader bound by the amendment"
    )

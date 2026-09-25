from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import liquidity_mean_reversion_selection as lmr

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "orchestration" / "external_replication" / "eth_tuesday_drift_runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("eth_tuesday_drift_runner_protected_opacity", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_loader_never_uses_full_cache_parser_that_decodes_protected_tail(monkeypatch):
    """Stage-1 may authenticate the whole blob but must not deserialize protected OHLCV.

    The canonical Cohort preflight already provides a protected-safe development-only
    parser.  This regression forbids the legacy full-cache loader because it parses and
    validates every OHLCV row before the Stage-1 runner later filters the protected tail.
    """
    runner = _load_runner()

    def _forbidden_full_cache(*_args, **_kwargs):
        raise AssertionError(
            "unsafe full-cache parser invoked: protected OHLCV would be deserialized before filtering"
        )

    monkeypatch.setattr(lmr, "_load_frozen_cache", _forbidden_full_cache)
    rows = runner.load_frozen_eth_rows()

    assert rows
    protected_ms = int(runner.PROTECTED_OOS_START.timestamp() * 1000)
    assert all(int(row["ts"]) < protected_ms for row in rows)

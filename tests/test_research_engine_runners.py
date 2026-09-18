import json
import pytest
from research_engines.contract import CrossEngineContract
from research_engines.dataset import canonical_bars, data_fingerprint
from research_engines.lean_adapter import write_lean_contract

def bars():
    return [
        {"ts": 1, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 5},
        {"ts": 2, "open": 10.5, "high": 12, "low": 10, "close": 11, "volume": 6},
    ]

def test_dataset_fingerprint_is_deterministic_and_chronological():
    assert data_fingerprint(bars()) == data_fingerprint(bars())
    with pytest.raises(ValueError):
        canonical_bars(list(reversed(bars())))

def test_lean_contract_contains_no_authority(tmp_path):
    rows = bars()
    contract = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", data_fingerprint(rows), 10)
    path = write_lean_contract(contract, tmp_path / "contract.json")
    payload = json.loads(open(path, encoding="utf-8").read())
    assert payload["contract_fingerprint"] == contract.fingerprint()
    assert payload["research_only"] is True
    assert payload["trade_authority"] is False

def test_nautilus_requires_executed_evidence(monkeypatch):
    import research_engines.nautilus_adapter as adapter
    monkeypatch.setattr(adapter, "require_engine", lambda name: {})
    rows = bars()
    contract = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", data_fingerprint(rows), 10)
    with pytest.raises(RuntimeError):
        adapter.run_nautilus(contract, rows, lambda **kwargs: {"executed": False, "trades": []})

def test_canonical_evidence_has_no_authority():
    from research_engines.evidence import evidence
    rows = bars()
    contract = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", data_fingerprint(rows), 10)
    result = evidence("test", contract, [])
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert {"return_pct", "win_rate", "ending_equity"} <= set(result["metrics"])

def test_preflight_uses_single_capability_source(monkeypatch):
    import research_engines.runner as runner
    state = {
        "vectorbt": {"available": True},
        "nautilus": {"available": True},
        "lean": {"available": True},
    }
    monkeypatch.setattr(runner, "engine_availability", lambda: state)
    result = runner.preflight()
    assert result["ok"] is True
    assert result["status"] == "READY"
    assert result["blockers"] == []
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False

def test_preflight_reports_missing_runtime(monkeypatch):
    import research_engines.runner as runner
    state = {
        "vectorbt": {"available": True},
        "nautilus": {"available": False},
        "lean": {"available": False},
    }
    monkeypatch.setattr(runner, "engine_availability", lambda: state)
    result = runner.preflight()
    assert result["ok"] is False
    assert result["status"] == "WAIT_RESEARCH_ONLY"
    assert any("nautilus_trader" in x for x in result["blockers"])
    assert any("LEAN CLI" in x for x in result["blockers"])

import json
from pathlib import Path

import pytest

from research_engines.contract import CrossEngineContract
from research_engines.dataset import canonical_bars, data_fingerprint
from research_engines.lean_adapter import write_lean_contract


def bars():
    return [
        {"ts": 1, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 5},
        {"ts": 2, "open": 10.5, "high": 12, "low": 10, "close": 11, "volume": 6},
    ]


def contract():
    rows = bars()
    return CrossEngineContract(
        "strategy", "BTC-USDT", "1H", "trend", data_fingerprint(rows), 10
    )


def real_engine_fixture():
    hour_ns = 3_600_000_000_000
    start = 1_700_000_000_000_000_000
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    rows = [
        {
            "ts": start + i * hour_ns,
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000.0,
        }
        for i, close in enumerate(closes)
    ]
    frozen = CrossEngineContract(
        strategy_fingerprint="ci-frozen-long",
        symbol="BTC-USDT",
        timeframe="1H",
        strategy_family="trend",
        data_fingerprint=data_fingerprint(rows),
        cost_bps_round_trip=0.0,
        decision_lag_bars=1,
        direction="long",
        validation_quantity=1.0,
        validation_initial_capital=100000.0,
    )
    entries = [True, False, False, False, False]
    exits = [False, False, True, False, False]
    return rows, frozen, entries, exits



def write_lean_manifest(project, launcher_config="/tmp/config.json"):
    payload = {
        "config": launcher_config,
        "algorithm-type-name": "FrozenPathResearchAlgorithm",
        "algorithm-language": "CSharp",
        "algorithm-location": "/tmp/algorithm.dll",
        "data-folder": "/tmp/data",
        "close-automatically": True,
    }
    (project / "lean_args.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_dataset_fingerprint_is_deterministic_and_chronological():
    assert data_fingerprint(bars()) == data_fingerprint(bars())
    with pytest.raises(ValueError):
        canonical_bars(list(reversed(bars())))


def test_lean_contract_contains_no_authority(tmp_path):
    frozen = contract()
    path = write_lean_contract(frozen, tmp_path / "contract.json")
    payload = json.loads(open(path, encoding="utf-8").read())
    assert payload["contract_fingerprint"] == frozen.fingerprint()
    assert payload["research_only"] is True
    assert payload["trade_authority"] is False


def test_source_built_lean_is_detected(monkeypatch, tmp_path):
    import research_engines.availability as availability

    launcher = tmp_path / "QuantConnect.Lean.Launcher.dll"
    launcher.write_text("test", encoding="utf-8")
    monkeypatch.setenv("LEAN_LAUNCHER_DLL", str(launcher))
    monkeypatch.setattr(
        availability.shutil,
        "which",
        lambda name: "/usr/bin/dotnet" if name == "dotnet" else None,
    )
    runtime = availability.lean_runtime()
    assert runtime["available"] is True
    assert runtime["mode"] == "source_launcher"
    assert runtime["launcher_dll"] == str(launcher.resolve())


def test_lean_source_launcher_requires_normalized_frozen_evidence(
    monkeypatch, tmp_path
):
    import research_engines.lean_adapter as adapter

    launcher = tmp_path / "QuantConnect.Lean.Launcher.dll"
    launcher.write_text("test", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    manifest = write_lean_manifest(project)
    frozen = contract()
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "executed": True,
                "contract_fingerprint": frozen.fingerprint(),
                "trades": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        adapter,
        "lean_runtime",
        lambda: {
            "available": True,
            "mode": "source_launcher",
            "executable": "/usr/bin/dotnet",
            "launcher_dll": str(launcher),
        },
    )

    seen = {}

    class Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs["cwd"]
        seen["shell"] = kwargs["shell"]
        return Proc()

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    out = adapter.run_lean_project(frozen, project, result)
    expected = ["/usr/bin/dotnet", str(launcher.resolve())]
    for key in (
        "config",
        "algorithm-type-name",
        "algorithm-language",
        "algorithm-location",
        "data-folder",
        "close-automatically",
    ):
        value = manifest[key]
        if isinstance(value, bool):
            value = "true" if value else "false"
        expected.extend([f"--{key}", str(value)])
    assert seen["argv"] == expected
    assert Path(seen["cwd"]) == launcher.parent
    assert seen["shell"] is False
    assert out["ok"] is True
    assert out["execution_mode"] == "lean_source_launcher"
    assert out["trade_authority"] is False
    assert out["promotion_authority"] is False


def test_lean_rejects_wrong_contract_fingerprint(monkeypatch, tmp_path):
    import research_engines.lean_adapter as adapter

    launcher = tmp_path / "QuantConnect.Lean.Launcher.dll"
    launcher.write_text("test", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    write_lean_manifest(project)
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {"executed": True, "contract_fingerprint": "wrong", "trades": []}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        adapter,
        "lean_runtime",
        lambda: {
            "available": True,
            "mode": "source_launcher",
            "executable": "/usr/bin/dotnet",
            "launcher_dll": str(launcher),
        },
    )

    class Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(RuntimeError, match="frozen contract"):
        adapter.run_lean_project(contract(), project, result)


def test_nautilus_requires_executed_evidence(monkeypatch):
    import research_engines.nautilus_adapter as adapter

    monkeypatch.setattr(adapter, "require_engine", lambda name: {})
    rows = bars()
    frozen = contract()
    with pytest.raises(RuntimeError):
        adapter.run_nautilus(
            frozen,
            rows,
            [False, False],
            [False, False],
            engine_runner=lambda **kwargs: {
                "executed": False,
                "trades": [],
                "bars_processed": len(rows),
            },
        )


def test_real_vectorbt_and_nautilus_reproduce_same_frozen_trade():
    pytest.importorskip("vectorbt")
    pytest.importorskip("nautilus_trader")

    from research_engines.nautilus_adapter import run_nautilus
    from research_engines.protocol import reconcile
    from research_engines.vectorbt_adapter import run_vectorbt

    rows, frozen, entries, exits = real_engine_fixture()
    vector = run_vectorbt(frozen, rows, entries, exits)
    nautilus = run_nautilus(frozen, rows, entries, exits)

    assert vector["trades"], vector
    assert nautilus["trades"], nautilus
    assert vector["trades"][0]["entry_ts"] == rows[1]["ts"]
    assert vector["trades"][0]["exit_ts"] == rows[3]["ts"]

    result = reconcile(
        {"vectorbt": vector, "nautilus": nautilus},
        required=("vectorbt", "nautilus"),
        price_tolerance=1e-8,
        pnl_tolerance=1e-6,
        metric_tolerance=1e-6,
    )
    assert result["ok"], {
        "reconciliation": result,
        "vectorbt": vector,
        "nautilus": nautilus,
    }


def test_canonical_evidence_has_no_authority():
    from research_engines.evidence import evidence

    result = evidence("test", contract(), [])
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
    assert any("LEAN_LAUNCHER_DLL" in x for x in result["blockers"])

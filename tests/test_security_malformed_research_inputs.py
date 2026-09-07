"""Adversarial checks for fail-closed handling of research evidence.

These tests intentionally use metrics that must never make a strategy live-ready.
"""

import json

import pytest

import research_runner
from strategy_families import _quality_gate


def _metrics(trades=20, avg=0.10, profit_factor=1.30, drawdown=5.0):
    return {
        "trades": trades,
        "win_rate_pct": 50.0,
        "avg_trade_pct": avg,
        "sum_net_returns_pct": 2.0,
        "profit_factor": profit_factor,
        "max_drawdown_pct": drawdown,
    }


def _research_status(gate):
    return "ELIGIBLE_OOS" if gate["passed"] else "RESEARCH_ONLY"


def test_nan_metric_with_invalid_evidence_count_remains_research_only():
    """NaN must not rescue a candidate whose OOS evidence is invalid."""
    gate = _quality_gate(
        _metrics(trades=30),
        _metrics(trades=-1, avg=float("nan")),
        _metrics(trades=12),
    )

    assert gate["passed"] is False
    assert gate["eligible_for_live_ensemble"] is False
    assert _research_status(gate) == "RESEARCH_ONLY"
    assert "validation_trades<6" in gate["reasons"]


def test_infinite_drawdown_is_rejected_without_crashing():
    gate = _quality_gate(
        _metrics(trades=30),
        _metrics(trades=12, drawdown=float("inf")),
        _metrics(trades=12),
    )

    assert gate["passed"] is False
    assert gate["eligible_for_live_ensemble"] is False
    assert _research_status(gate) == "RESEARCH_ONLY"
    assert "validation_drawdown>18" in gate["reasons"]


@pytest.mark.parametrize("bad_count", [-10, -1, 0, 5])
def test_invalid_validation_evidence_counts_are_rejected(bad_count):
    gate = _quality_gate(
        _metrics(trades=30),
        _metrics(trades=bad_count),
        _metrics(trades=12),
    )

    assert gate["passed"] is False
    assert gate["eligible_for_live_ensemble"] is False
    assert _research_status(gate) == "RESEARCH_ONLY"
    assert "validation_trades<6" in gate["reasons"]


def test_missing_registry_status_and_gate_do_not_get_promoted(monkeypatch, tmp_path):
    """Malformed registry records must be ignored rather than crashing a run."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RESEARCH_SYMBOLS", "TEST-USDT")
    monkeypatch.setenv("RESEARCH_TIMEFRAMES", "1H")
    monkeypatch.setattr(research_runner, "run_backtest", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(research_runner, "walk_forward", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        research_runner,
        "evaluate_strategy_registry",
        lambda *args, **kwargs: {
            "ok": True,
            "registry": [
                {
                    "strategy_family": "malformed-test-family",
                    # Deliberately missing status and quality_gate.
                    "validation": {"trades": 12, "avg_trade_pct": float("nan")},
                    "holdout_test": {"trades": -1},
                }
            ],
        },
    )

    research_runner.main()

    payload = json.loads(
        (tmp_path / "research_output" / "strategy_registry.json").read_text(encoding="utf-8")
    )
    assert payload["eligible_strategy_count"] == 0
    assert payload["eligible_strategies"] == []

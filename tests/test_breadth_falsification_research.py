import json
from datetime import datetime, timezone

from breadth_falsification_research import evaluate_breadth_horizon
from point_in_time_universe import load_manifest

DAY_MS = 24 * 60 * 60 * 1000


def _manifest(tmp_path, symbols, start_ms):
    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "provenance": {"source": "test historical point-in-time archive", "captured_at": "2026-01-01T00:00:00Z"},
        "snapshots": [{"effective_from": start, "effective_to": None, "symbols": symbols}],
    }
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_manifest(str(path))


def _histories(symbols, start_ms, daily_returns):
    histories = {}
    for symbol in symbols:
        close = 100.0
        rows = [{"ts": start_ms, "close": close}]
        for index, ret in enumerate(daily_returns, start=1):
            close *= 1.0 + ret
            rows.append({"ts": start_ms + index * DAY_MS, "close": close})
        histories[symbol] = rows
    return histories


def _dataset(histories, manifest):
    return {
        "research_only": True,
        "candidate_id": "DATA-BREADTH-001",
        "available": True,
        "histories": histories,
        "universe_manifest": manifest,
    }


def test_invalid_dataset_fails_closed():
    result = evaluate_breadth_horizon({"research_only": True, "candidate_id": "OTHER"}, 24)
    assert result["available"] is False
    assert result["reason"] == "invalid_research_dataset"


def test_missing_point_in_time_manifest_fails_closed():
    result = evaluate_breadth_horizon(_dataset({}, {"valid": False, "reason": "manifest_missing"}), 24)
    assert result["available"] is False
    assert result["reason"] == "manifest_missing"


def test_missing_historical_universe_member_is_rejected_before_scoring(tmp_path):
    start_ms = 1_700_000_000_000
    manifest_symbols = [f"A{i}-USDT" for i in range(16)]
    fetched_symbols = manifest_symbols[:-1]
    manifest = _manifest(tmp_path, manifest_symbols, start_ms)
    histories = _histories(fetched_symbols, start_ms, [0.01] * 30)

    result = evaluate_breadth_horizon(_dataset(histories, manifest), 24)

    assert result["available"] is False
    assert result["reason"] == "point_in_time_universe_incomplete_or_history_mismatch"
    assert result["point_in_time_universe"]["missing_historical_member_symbols"] == [manifest_symbols[-1]]


def test_chronological_breadth_scoring_exposes_profitability_metrics_without_authority(tmp_path):
    start_ms = 1_700_000_000_000
    symbols = [f"A{i}-USDT" for i in range(15)]
    # Persistent five-day participation regimes make trailing breadth informative
    # about the next daily market move without any threshold fitting.
    signs = ([1] * 5 + [-1] * 5) * 4
    returns = [0.012 if sign > 0 else -0.010 for sign in signs]
    manifest = _manifest(tmp_path, symbols, start_ms)
    histories = _histories(symbols, start_ms, returns)

    result = evaluate_breadth_horizon(_dataset(histories, manifest), 24, cost_bps=10.0)

    assert result["available"] is True
    assert result["candidate_id"] == "DATA-BREADTH-001"
    assert result["non_overlapping"] is True
    assert result["threshold_tuning"] is False
    assert result["oos_samples"] >= 8
    assert result["point_in_time_universe"]["survivorship_safe"] is True
    assert result["promotion_authority"] is False
    assert result["production_authority"] is False
    canonical = result["cost_stress"]["1x"]
    assert canonical["avg_net_bps"] is not None
    assert canonical["profit_factor"] is not None
    assert canonical["win_rate"] is not None
    assert canonical["max_drawdown_bps"] >= 0
    assert "incremental_vs_baseline_bps" in canonical
    assert set(result["cost_stress"]) == {"1x", "2x", "3x"}


def test_primary_sample_floor_is_checked_before_scoring(tmp_path):
    start_ms = 1_700_000_000_000
    symbols = [f"A{i}-USDT" for i in range(15)]
    manifest = _manifest(tmp_path, symbols, start_ms)
    histories = _histories(symbols, start_ms, [0.01, 0.01, -0.01, -0.01] * 4)

    result = evaluate_breadth_horizon(_dataset(histories, manifest), 24 * 7, cost_bps=10.0)

    assert result["available"] is False
    assert result["reason"] in {
        "insufficient_non_overlapping_causal_samples",
        "insufficient_oos_samples_before_scoring",
    }

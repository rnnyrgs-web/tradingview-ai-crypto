from datetime import datetime, timedelta, timezone

from research_microstructure_veto import build_microstructure_veto
from research_selective_wait_fusion import build_selective_wait_fusion


def _row(*, horizon, index, return_pct, micro_state):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    spacing_days = 1 if horizon == "24h" else 8
    forecast = start + timedelta(days=index * spacing_days)
    horizon_delta = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    due = forecast + horizon_delta
    micro = {
        "reliable": True,
        "spread_bps": 5.0,
        "visible_quote_depth": 100000.0,
        "depth_imbalance": 0.0,
    }
    if micro_state == "adverse_imbalance":
        micro["depth_imbalance"] = -0.5
    return {
        "forecast_at": forecast.isoformat(),
        "due_at": due.isoformat(),
        "resolved_at": (due + timedelta(minutes=1)).isoformat(),
        "horizon": horizon,
        "symbol": f"ASSET-{index}",
        "correct": return_pct > 0,
        "directional_return_pct": return_pct,
        "score": 85,
        "strategy_identity": "profitability-regression",
        "market_regime": "TREND_UP",
        "direction": "LONG",
        "microstructure": micro,
    }


def test_microstructure_profitability_never_pools_24h_and_7d():
    rows = []
    for horizon in ("24h", "7d"):
        for i in range(8):
            rows.append(_row(horizon=horizon, index=i, return_pct=0.6, micro_state="normal"))

    # Strong 24h execution economics must not mask economically harmful 7d
    # adverse execution. A pooled evaluator would average these together.
    for i in range(8, 16):
        rows.append(_row(horizon="24h", index=i, return_pct=2.0, micro_state="adverse_imbalance"))
        rows.append(_row(horizon="7d", index=i, return_pct=-1.0, micro_state="adverse_imbalance"))

    report = build_microstructure_veto(rows)
    assert report["horizon_pooling_allowed"] is False
    assert report["normal_baseline_ready_by_horizon"] == {"24h": True, "7d": True}

    adverse_24h = next(
        row for row in report["groups"]
        if row["horizon"] == "24h" and row["microstructure_state"] == "adverse_imbalance"
    )
    adverse_7d = next(
        row for row in report["groups"]
        if row["horizon"] == "7d" and row["microstructure_state"] == "adverse_imbalance"
    )
    assert adverse_24h["candidate_status"] == "NO_VETO_EVIDENCE"
    assert adverse_24h["after_cost_expectancy_pct"] > 0
    assert adverse_7d["candidate_status"] == "RESTRICTIVE_VETO_CANDIDATE"
    assert adverse_7d["after_cost_expectancy_pct"] < 0
    assert adverse_7d["incremental_expectancy_vs_normal_pct"] < 0
    assert report["trade_authority"] is False


def test_selective_wait_keeps_microstructure_hypotheses_horizon_specific():
    fusion = build_selective_wait_fusion(
        meta_wait={},
        regime_strategy={},
        economic_calibration={},
        microstructure_veto={
            "groups": [
                {
                    "horizon": "24h",
                    "microstructure_state": "adverse_imbalance",
                    "candidate_status": "RESTRICTIVE_VETO_CANDIDATE",
                    "samples": 8,
                },
                {
                    "horizon": "7d",
                    "microstructure_state": "adverse_imbalance",
                    "candidate_status": "RESTRICTIVE_VETO_CANDIDATE",
                    "samples": 8,
                },
            ]
        },
        error_attribution={},
    )
    ids = {row["hypothesis_id"] for row in fusion["restrictive_hypotheses"]}
    assert "microstructure:24h:adverse_imbalance" in ids
    assert "microstructure:7d:adverse_imbalance" in ids
    assert "microstructure:adverse_imbalance" not in ids
    assert fusion["trade_authority"] is False

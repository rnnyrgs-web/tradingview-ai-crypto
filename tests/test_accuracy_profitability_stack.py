from datetime import datetime, timedelta, timezone

from research_cross_sectional_diagnostics import build_cross_sectional_diagnostics
from research_economic_calibration import build_economic_calibration
from research_ensemble_diversity import build_ensemble_diversity
from research_error_attribution import build_error_attribution
from research_microstructure_veto import build_microstructure_veto
from research_selective_wait_fusion import build_selective_wait_fusion


def _rows(n=60, *, return_pct=1.0, correct=True, strategy="s1", symbol="XRP-USDT"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        origin = start + timedelta(days=i)
        due = origin + timedelta(hours=24)
        out.append({
            "forecast_at": origin.isoformat(),
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "horizon": "24h",
            "symbol": symbol,
            "correct": correct,
            "directional_return_pct": return_pct,
            "score": 85,
            "strategy_identity": strategy,
            "market_regime": "TREND_UP",
            "direction": "LONG",
        })
    return out


def test_economic_calibration_positive_and_negative_keep_oos_sealed():
    positive = build_economic_calibration(_rows())
    h = positive["horizons"]["24h"]
    band = next(x for x in h["confidence_bands"] if x["confidence_band"] == "80-89")
    assert band["candidate_status"] == "POSITIVE_ECONOMIC_CALIBRATION_CANDIDATE"
    assert positive["untouched_oos_outcomes_scored"] is False
    assert positive["trade_authority"] is False

    negative = build_economic_calibration(_rows(return_pct=-1.0, correct=False))
    band = next(x for x in negative["horizons"]["24h"]["confidence_bands"] if x["confidence_band"] == "80-89")
    assert band["candidate_status"] == "RESTRICTIVE_WAIT_CANDIDATE"


def test_cross_sectional_never_backfills_missing_fields():
    report = build_cross_sectional_diagnostics(_rows())
    assert report["available_preforecast_fields"] == []
    assert "cross_sectional_rank" in report["missing_fields"]
    assert report["historical_backfill_allowed"] is False

    rows = _rows()
    for i, row in enumerate(rows):
        row["cross_sectional_rank"] = 3 if i % 2 == 0 else 8
        row["residual_momentum_score"] = 0.8
    report = build_cross_sectional_diagnostics(rows)
    assert "cross_sectional_rank" in report["available_preforecast_fields"]
    assert any(g["feature"] == "residual_momentum_score" for g in report["groups"])
    assert report["trade_authority"] is False


def test_microstructure_veto_requires_real_prospective_fields():
    missing = build_microstructure_veto(_rows(return_pct=-1.0, correct=False))
    assert missing["samples_with_microstructure"] == 0
    assert missing["historical_orderbook_reconstruction_allowed"] is False

    rows = _rows(return_pct=-1.0, correct=False)
    for row in rows:
        row["microstructure"] = {
            "reliable": True,
            "spread_bps": 50.0,
            "visible_quote_depth": 100000.0,
            "depth_imbalance": 0.0,
        }
    report = build_microstructure_veto(rows)
    wide = next(x for x in report["groups"] if x["microstructure_state"] == "wide_spread")
    assert wide["candidate_status"] == "RESTRICTIVE_VETO_CANDIDATE"
    assert report["broker_connected"] is False


def test_error_attribution_and_ensemble_diversity_are_research_only():
    errors = _rows(n=20, return_pct=-1.0, correct=False)
    for row in errors:
        row["score"] = 90
    attribution = build_error_attribution(errors)
    assert attribution["attribution_counts"]["high_confidence_false_positive"] == 20
    assert attribution["trade_authority"] is False

    rows = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(12):
        due = start + timedelta(days=i + 1)
        for strategy in ("s1", "s2"):
            rows.append({
                "horizon": "24h",
                "symbol": "XRP-USDT",
                "due_at": due.isoformat(),
                "resolved_at": (due + timedelta(minutes=1)).isoformat(),
                "strategy_identity": strategy,
                "correct": i % 3 != 0,
            })
    diversity = build_ensemble_diversity(rows)
    pair = diversity["pairs"][0]
    assert pair["matched_samples"] == 12
    assert pair["candidate_status"] == "REDUNDANT_MECHANISM_RESEARCH_CANDIDATE"
    assert pair["treat_as_independent_confirmation"] is False
    assert diversity["promotion_authority"] is False


def test_selective_wait_fusion_only_nominates_experiments():
    fusion = build_selective_wait_fusion(
        meta_wait={"groups": [{"dimension": "direction", "group": "LONG", "samples": 20, "ready_for_research": True, "after_cost_expectancy_pct": -0.2}]},
        regime_strategy={"horizons": {"24h": {"pairs": [{"market_regime": "TREND_UP", "strategy_identity": "s1", "candidate_status": "RESTRICTIVE_WAIT_CANDIDATE", "validation": {"samples": 6}}]}}},
        economic_calibration={"horizons": {"24h": {"confidence_bands": [{"confidence_band": "80-89", "candidate_status": "RESTRICTIVE_WAIT_CANDIDATE", "validation": {"samples": 6}}]}}},
        microstructure_veto={"groups": [{"microstructure_state": "wide_spread", "candidate_status": "RESTRICTIVE_VETO_CANDIDATE", "samples": 9}]},
        error_attribution={"research_priorities": [{"reason": "high_confidence_false_positive", "independent_error_samples": 7}]},
    )
    assert len(fusion["restrictive_hypotheses"]) == 5
    assert fusion["untouched_oos_opened"] is False
    assert fusion["trade_authority"] is False
    assert all(x["recommended_action"] == "PREDECLARE_RESTRICTIVE_WAIT_EXPERIMENT" for x in fusion["restrictive_hypotheses"])

from datetime import datetime, timedelta, timezone

from research_meta_signal_trust import build_meta_signal_trust


def _rows(n=120, *, horizon="24h", with_consensus=True, production_action="TRADE"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = timedelta(days=1 if horizon == "24h" else 7)
    horizon_delta = timedelta(hours=24 if horizon == "24h" else 24 * 7)
    rows = []
    for i in range(n):
        origin = start + step * i
        due = origin + horizon_delta
        trusted = i % 2 == 0
        row = {
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "horizon": horizon,
            "direction": "LONG" if i % 3 else "SHORT",
            "correct": True if trusted else (i % 4 != 1),
            "directional_return_pct": 1.0 if trusted else (-0.5 if i % 4 == 1 else 0.25),
            "score": 90 if trusted else 70,
            "market_regime": "TREND_UP",
            "strategy_identity": "s1",
            "action_at_forecast": production_action,
        }
        if with_consensus and trusted:
            row.update({
                "market_consensus_timestamp_safe": True,
                "market_consensus_reliable": True,
                "market_consensus_source_count": 3,
                "market_consensus_required_source_count": 2,
            })
        rows.append(row)
    return rows


def _profile(report, horizon, name):
    return next(row for row in report["horizons"][horizon]["profiles"] if row["profile"] == name)


def test_a_plus_profile_requires_strong_dev_validation_and_cost_stress():
    report = build_meta_signal_trust(_rows())
    candidate = _profile(report, "24h", "HIGH_CONFIDENCE_CONSENSUS")
    assert candidate["candidate_status"] == "A_PLUS_PROFILE_RESEARCH_CANDIDATE"
    assert candidate["development_precision_lift_vs_directional_baseline"] >= 0.02
    assert candidate["validation_precision_lift_vs_directional_baseline"] >= 0.02
    assert candidate["development"]["worst_case_after_cost_expectancy_pct"] > 0
    assert candidate["validation"]["worst_case_after_cost_expectancy_pct"] > 0


def test_missing_consensus_fails_closed_instead_of_inventing_a_plus():
    report = build_meta_signal_trust(_rows(with_consensus=False))
    candidate = _profile(report, "24h", "HIGH_CONFIDENCE_CONSENSUS")
    assert candidate["candidate_status"] == "INSUFFICIENT_INDEPENDENT_EVIDENCE"
    assert candidate["development"]["samples"] == 0
    assert candidate["validation"]["samples"] == 0


def test_production_wait_shadow_directions_are_research_eligible_without_authority():
    report = build_meta_signal_trust(_rows(production_action="WAIT"))
    baseline = _profile(report, "24h", "BASE_ACTIONABLE")
    candidate = _profile(report, "24h", "HIGH_CONFIDENCE_CONSENSUS")
    assert baseline["development"]["samples"] > 0
    assert baseline["development"]["production_wait_rows_evaluated_research_only"] == baseline["development"]["samples"]
    assert candidate["development"]["samples"] > 0
    assert report["production_wait_rows_may_be_evaluated"] is True
    assert report["production_wait_mutation_allowed"] is False
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["live_label_allowed"] is False


def test_rows_without_long_short_shadow_direction_are_not_research_eligible():
    rows = _rows(production_action="WAIT")
    for row in rows:
        row["direction"] = "WAIT"
    report = build_meta_signal_trust(rows)
    baseline = _profile(report, "24h", "BASE_ACTIONABLE")
    assert baseline["development"]["samples"] == 0
    assert baseline["validation"]["samples"] == 0


def test_horizons_are_separate_and_oos_remains_sealed():
    report = build_meta_signal_trust(_rows(horizon="24h") + _rows(horizon="7d"))
    assert report["horizons"]["24h"]["independent_samples"] > 0
    assert report["horizons"]["7d"]["independent_samples"] > 0
    assert report["untouched_oos_outcomes_scored"] is False
    assert report["untouched_oos_samples_sealed"] > 0
    assert report["live_label_allowed"] is False
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False


def test_supporting_diagnostics_are_not_counted_as_independent_confirmation():
    report = build_meta_signal_trust(
        _rows(),
        regime_strategy={"horizons": {"24h": {"pairs": [{"candidate_status": "PROSPECTIVE_SHADOW_ROUTER_CANDIDATE"}]}}},
        ensemble_diversity={"pairs": [{"candidate_status": "DIVERSE"}]},
        microstructure_veto={"samples_with_microstructure": 12},
    )
    readiness = report["supporting_evidence_readiness"]
    assert readiness["regime_router_candidates"] == 1
    assert readiness["ensemble_diversity_pairs_measured"] == 1
    assert readiness["prospective_microstructure_samples"] == 12
    assert "not counted as independent confirmation" in readiness["policy"]

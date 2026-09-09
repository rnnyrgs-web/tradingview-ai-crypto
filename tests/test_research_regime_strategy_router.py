from datetime import datetime, timedelta, timezone

from research_regime_strategy_router import build_regime_strategy_router


def _rows(n=60, *, regime="TREND_UP", strategy="s1", return_pct=1.0, correct=True):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        origin = start + timedelta(days=i)
        due = origin + timedelta(hours=24)
        out.append({
            "horizon": "24h",
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "correct": correct,
            "directional_return_pct": return_pct,
            "market_regime": regime,
            "strategy_identity": strategy,
        })
    return out


def test_positive_pair_is_shadow_candidate_but_oos_stays_sealed():
    report = build_regime_strategy_router(_rows())
    h = report["horizons"]["24h"]
    pair = h["pairs"][0]
    assert pair["candidate_status"] == "PROSPECTIVE_SHADOW_ROUTER_CANDIDATE"
    assert h["untouched_oos_samples_sealed"] > 0
    assert report["untouched_oos_outcomes_scored"] is False
    assert "untouched_oos" not in pair
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False


def test_negative_pair_becomes_restrictive_wait_candidate():
    report = build_regime_strategy_router(_rows(return_pct=-1.0, correct=False))
    pair = report["horizons"]["24h"]["pairs"][0]
    assert pair["candidate_status"] == "RESTRICTIVE_WAIT_CANDIDATE"
    assert pair["requires_untouched_oos"] is True


def test_insufficient_pair_fails_closed():
    report = build_regime_strategy_router(_rows(n=12))
    pair = report["horizons"]["24h"]["pairs"][0]
    assert pair["candidate_status"] == "INSUFFICIENT_INDEPENDENT_SAMPLES"


def test_overlapping_forecasts_do_not_create_false_sample_size():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(60):
        origin = start + timedelta(minutes=15 * i)
        due = origin + timedelta(hours=24)
        rows.append({
            "horizon": "24h", "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "correct": True, "directional_return_pct": 1.0,
            "market_regime": "TREND_UP", "strategy_identity": "s1",
        })
    report = build_regime_strategy_router(rows)
    assert report["horizons"]["24h"]["independent_samples"] == 1


def test_missing_pair_identity_is_not_promoted():
    rows = _rows()
    for row in rows:
        row["market_regime"] = None
        row["strategy_identity"] = None
    report = build_regime_strategy_router(rows)
    pair = report["horizons"]["24h"]["pairs"][0]
    assert pair["market_regime"] == "unknown"
    assert pair["strategy_identity"] == "unknown"
    # Unknown provenance can be diagnosed but never itself grants authority.
    assert pair["trade_authority"] is False
    assert pair["promotion_authority"] is False

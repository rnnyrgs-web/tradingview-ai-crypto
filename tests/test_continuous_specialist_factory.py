from datetime import datetime, timedelta, timezone

from continuous_specialist_factory import SPECIALISTS, build_specialist_snapshot


def _rows(count=40):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        horizon = "24h" if i % 2 == 0 else "7d"
        span = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
        origin = start + timedelta(days=i * 8)
        due = origin + span
        rows.append(
            {
                "symbol": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "LINK-USDT"][i % 5],
                "horizon": horizon,
                "direction": "BUY" if i % 3 else "SELL",
                "market_regime": ["BULL", "BEAR", "SIDEWAYS", "UNKNOWN"][i % 4],
                "score": 55 + (i % 5) * 10,
                "correct": i % 4 != 0,
                "due_at": due.isoformat(),
                "resolved_at": due.isoformat(),
                "directional_return_pct": 1.0 if i % 4 != 0 else -1.0,
                "strategy_identity": f"strategy-{i % 3}",
            }
        )
    return rows


def test_factory_expands_to_many_logical_workers_without_authority():
    assert len(SPECIALISTS) >= 30
    reports = build_specialist_snapshot(_rows())
    assert len(reports) == len(SPECIALISTS)
    assert reports["btc-diagnostics"]["resolved_rows"] > 0
    assert reports["24h-diagnostics"]["resolved_rows"] > 0
    assert reports["7d-diagnostics"]["resolved_rows"] > 0
    for report in reports.values():
        assert report["research_only"] is True
        assert report["trade_authority"] is False
        assert report["promotion_authority"] is False
        assert report["automatic_tuning"] is False
        assert report["raw_rows_are_independent"] is False
        assert report["independence_claims_use_full_horizon_deoverlap"] is True


def test_selective_precision_workers_use_fixed_non_overlapping_assessment():
    reports = build_specialist_snapshot(_rows(80))
    for name in ("selective-precision-24h", "selective-precision-7d"):
        selective = reports[name]["selective_precision"]
        assert selective["thresholds_predeclared"] is True
        assert selective["non_overlapping_full_horizon_samples_only"] is True
        assert selective["trade_authority"] is False
        assert selective["promotion_authority"] is False


def test_empty_ledger_fails_closed_to_awaiting_evidence():
    reports = build_specialist_snapshot([])
    assert reports
    assert all(report["status"] == "awaiting_resolved_evidence" for report in reports.values())
    assert all(report["top_falsifiable_hypothesis"] is None for report in reports.values())

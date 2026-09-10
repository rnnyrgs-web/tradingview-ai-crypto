import ffrizz_secondary_runner as runner
import research_adaptive_accuracy_runner as adaptive_runner


def test_v2_feature_diagnostics_run_in_existing_pass_without_persistence(monkeypatch):
    monkeypatch.setattr(runner, "build_universe", lambda: [{"symbol": "BTC-USD", "base": "BTC"}])
    candles = [{"ts": i * 3_600_000, "close": 100 + i} for i in range(1, 10)]
    monkeypatch.setattr(runner, "get_history", lambda *args, **kwargs: candles)
    oi_points = [{"ts": (i + 1) * 3_600_000, "value": 1000 + i} for i in range(1, 10)]
    monkeypatch.setattr(runner, "_oi_points", lambda base: oi_points)
    monkeypatch.setattr(
        runner,
        "score_shadow_signal",
        lambda *args, horizon=None, **kwargs: {
            "horizon": horizon,
            "bar": runner.HORIZON_PROFILES[horizon]["bar"],
            "direction": "NEUTRAL",
            "action": "WAIT",
            "score": 0.0,
            "independent_family_agreement": 0,
            "available_family_count": 0,
            "families": [],
        },
    )
    monkeypatch.setattr(
        runner,
        "chronological_backtest",
        lambda *args, **kwargs: {"signals": 0, "accuracy": None, "mean_net_pct": None},
    )

    seen = []

    def fake_v2(candles_arg, oi_arg, *, horizon, bar):
        seen.append((horizon, bar, candles_arg is candles, oi_arg is oi_points))
        return {
            "families": [
                {"family": "pb_ema", "available": True},
                {"family": "fvg", "available": True},
                {"family": "inside_bar", "available": True},
                {"family": "price_oi_correlation_v2", "available": True},
            ]
        }

    monkeypatch.setattr(runner, "score_shadow_signal_v2", fake_v2)
    report = runner.run(persist=False)

    assert seen == [
        ("6h", "1H", True, True),
        ("12h", "1H", True, True),
        ("24h", "1H", True, True),
    ]
    diagnostic = report["v2_oi_alignment_feature_availability"]
    assert diagnostic["system"] == "FFRIZZ_SECONDARY_V2_OI_CLOSE_END"
    assert diagnostic["trade_authority"] is False
    assert diagnostic["promotion_authority"] is False
    assert set(diagnostic["horizons"]) == {"6h", "12h", "24h"}
    assert diagnostic["horizons"]["24h"]["family_counts"]["price_oi_correlation_v2:available"] == 1
    assert report["forward_evidence"]["prediction_ledger_rows"] == []


def test_adaptive_summary_preserves_only_bounded_v2_counts(monkeypatch):
    v2 = {
        "system": "FFRIZZ_SECONDARY_V2_OI_CLOSE_END",
        "diagnostic_only": True,
        "symbol_level_data_exposed": False,
        "horizons": {
            "6h": {
                "signals_scored": 12,
                "family_counts": {
                    "price_oi_correlation_v2:available": 9,
                    "price_oi_correlation_v2:unavailable": 3,
                    "unapproved_key": 999,
                },
            },
            "48h": {"signals_scored": 12, "family_counts": {"price_oi_correlation_v2:available": 12}},
        },
    }
    monkeypatch.setattr(
        adaptive_runner,
        "run_ffrizz_secondary",
        lambda persist=True: {
            "system": "FFRIZZ_SECONDARY_V1",
            "generated_at": "2026-09-10T00:00:00+00:00",
            "forward_evidence": {
                "eligible_shadow_forecasts": 0,
                "non_overlapping_full_horizon_buckets": True,
                "wait_rows_persisted": False,
                "historical_oi_backfill_used": False,
                "abstention_diagnostics": {},
            },
            "v2_oi_alignment_feature_availability": v2,
        },
    )

    result = adaptive_runner._ffrizz_forward_collection()
    bounded = result["v2_oi_alignment_feature_availability"]
    assert result["ok"] is True
    assert set(bounded["horizons"]) == {"6h"}
    assert bounded["horizons"]["6h"]["signals_scored"] == 12
    assert bounded["horizons"]["6h"]["family_counts"] == {
        "price_oi_correlation_v2:available": 9,
        "price_oi_correlation_v2:unavailable": 3,
    }
    assert bounded["symbol_level_data_exposed"] is False
    assert bounded["trade_authority"] is False
    assert bounded["promotion_authority"] is False

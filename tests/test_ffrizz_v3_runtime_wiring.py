import continuous_coordinator as coordinator
import ffrizz_secondary_runner as runner
import research_adaptive_accuracy_runner as adaptive_runner


def test_v3_runs_in_existing_pass_and_reuses_cached_inputs(monkeypatch):
    monkeypatch.setattr(runner, "build_universe", lambda: [{"symbol": "BTC-USD", "base": "BTC"}])
    candles = [{"ts": i * 3_600_000, "close": 100 + i} for i in range(1, 10)]
    monkeypatch.setattr(runner, "get_history", lambda *args, **kwargs: candles)
    oi_points = [{"ts": (i + 1) * 3_600_000 + 1_000, "value": 1000 + i} for i in range(1, 10)]
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
    monkeypatch.setattr(runner, "score_shadow_signal_v2", lambda *args, **kwargs: {"families": []})

    seen = []

    def fake_v3(candles_arg, oi_arg, *, horizon, bar):
        seen.append((horizon, bar, candles_arg is candles, oi_arg is oi_points))
        return {
            "families": [
                {"family": "pb_ema", "available": True},
                {"family": "fvg", "available": True},
                {"family": "inside_bar", "available": True},
                {"family": "price_oi_correlation_v3", "available": False, "reason": "insufficient_causal_asof_overlap"},
            ],
            "symbol": "MUST_NOT_ESCAPE",
        }

    monkeypatch.setattr(runner, "score_shadow_signal_v3", fake_v3)
    report = runner.run(persist=False)

    assert seen == [
        ("6h", "1H", True, True),
        ("12h", "1H", True, True),
        ("24h", "1H", True, True),
    ]
    diagnostic = report["v3_oi_causal_asof_feature_availability"]
    assert diagnostic["system"] == "FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF"
    assert diagnostic["causal_asof_only"] is True
    assert diagnostic["future_price_used"] is False
    assert diagnostic["nearest_neighbor_used"] is False
    assert diagnostic["interpolation_used"] is False
    assert diagnostic["max_price_staleness_ms_exclusive"] == 3_600_000
    assert diagnostic["symbol_level_data_exposed"] is False
    assert "MUST_NOT_ESCAPE" not in repr(diagnostic)
    assert diagnostic["horizons"]["24h"]["family_counts"]["price_oi_correlation_v3:unavailable"] == 1
    assert diagnostic["horizons"]["24h"]["oi_unavailable_reason_counts"] == {
        "insufficient_causal_asof_overlap": 1
    }
    assert diagnostic["trade_authority"] is False
    assert diagnostic["promotion_authority"] is False
    assert report["forward_evidence"]["prediction_ledger_rows"] == []


def test_adaptive_summary_allowlists_v3_counts_and_reasons(monkeypatch):
    v3 = {
        "system": "FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF",
        "diagnostic_only": True,
        "symbol_level_data_exposed": False,
        "horizons": {
            "6h": {
                "signals_scored": 12,
                "family_counts": {
                    "price_oi_correlation_v3:available": 9,
                    "price_oi_correlation_v3:unavailable": 3,
                    "unapproved_key": 999,
                },
                "oi_unavailable_reason_counts": {
                    "insufficient_causal_asof_overlap": 3,
                    "SECRET_SYMBOL_BTC": 999,
                },
                "symbols": ["BTC-USD"],
            },
            "48h": {"signals_scored": 12, "family_counts": {"price_oi_correlation_v3:available": 12}},
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
            "v3_oi_causal_asof_feature_availability": v3,
        },
    )

    result = adaptive_runner._ffrizz_forward_collection()
    bounded = result["v3_oi_causal_asof_feature_availability"]
    assert result["ok"] is True
    assert set(bounded["horizons"]) == {"6h"}
    assert bounded["horizons"]["6h"]["family_counts"] == {
        "price_oi_correlation_v3:available": 9,
        "price_oi_correlation_v3:unavailable": 3,
    }
    assert bounded["horizons"]["6h"]["oi_unavailable_reason_counts"] == {
        "insufficient_causal_asof_overlap": 3
    }
    assert "BTC" not in repr(bounded)
    assert bounded["future_price_used"] is False
    assert bounded["trade_authority"] is False
    assert bounded["promotion_authority"] is False


def test_coordinator_reallowlists_v3_at_final_log_boundary():
    raw = {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "eligible_shadow_forecasts": 0,
                        "abstention_diagnostics": {},
                        "v3_oi_causal_asof_feature_availability": {
                            "diagnostic_only": True,
                            "horizons": {
                                "6h": {
                                    "signals_scored": 12,
                                    "family_counts": {
                                        "price_oi_correlation_v3:available": 10,
                                        "price_oi_correlation_v3:unavailable": 2,
                                        "rogue": 999,
                                    },
                                    "oi_unavailable_reason_counts": {
                                        "insufficient_causal_asof_overlap": 2,
                                        "BTC-USD": 999,
                                    },
                                    "symbols": ["BTC-USD"],
                                },
                            },
                        },
                    },
                },
            },
        },
        "supervisor": {},
    }

    bounded = coordinator.observability_log_payload(raw)["ffrizz_forward"]["v3_oi_causal_asof_feature_availability"]
    assert bounded["horizons"]["6h"]["family_counts"] == {
        "price_oi_correlation_v3:available": 10,
        "price_oi_correlation_v3:unavailable": 2,
    }
    assert bounded["horizons"]["6h"]["oi_unavailable_reason_counts"] == {
        "insufficient_causal_asof_overlap": 2
    }
    assert "BTC" not in repr(bounded)
    assert bounded["future_price_used"] is False
    assert bounded["nearest_neighbor_used"] is False
    assert bounded["interpolation_used"] is False
    assert bounded["trade_authority"] is False
    assert bounded["promotion_authority"] is False

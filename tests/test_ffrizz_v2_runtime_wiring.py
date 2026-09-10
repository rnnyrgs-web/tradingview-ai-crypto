import ffrizz_secondary_runner as runner


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

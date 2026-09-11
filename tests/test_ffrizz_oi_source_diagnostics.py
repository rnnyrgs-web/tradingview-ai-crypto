import ffrizz_secondary_runner as runner
import research_adaptive_accuracy_runner as adaptive_runner


def test_oi_points_classifies_existing_derivatives_result_without_extra_fetch(monkeypatch):
    calls = []

    def fake_history(base, limit=90):
        calls.append((base, limit))
        return {
            "open_interest_history": {"binance": []},
            "errors": [
                {"source": "binance_open_interest_history", "error_type": "HTTPStatusError"},
                {"source": "okx_funding", "error_type": "MUST_NOT_ESCAPE"},
            ],
        }

    monkeypatch.setattr(runner, "get_derivatives_history", fake_history)
    points = runner._oi_points("BTC")

    assert list(points) == []
    assert points.source_status == "http_error"
    assert calls == [("BTC", 90)]
    assert "MUST_NOT_ESCAPE" not in points.source_status


def test_oi_points_distinguishes_available_empty_and_timeout(monkeypatch):
    monkeypatch.setattr(
        runner,
        "get_derivatives_history",
        lambda *args, **kwargs: {
            "open_interest_history": {"binance": [{"ts": 1, "value": 2.0}]},
            "errors": [],
        },
    )
    assert runner._oi_points("BTC").source_status == "available"

    monkeypatch.setattr(
        runner,
        "get_derivatives_history",
        lambda *args, **kwargs: {"open_interest_history": {"binance": []}, "errors": []},
    )
    assert runner._oi_points("BTC").source_status == "valid_empty"

    monkeypatch.setattr(
        runner,
        "get_derivatives_history",
        lambda *args, **kwargs: {
            "open_interest_history": {"binance": []},
            "errors": [{"source": "binance_open_interest_history", "error_type": "ReadTimeout"}],
        },
    )
    assert runner._oi_points("BTC").source_status == "timeout"


def _patch_minimal_run_dependencies(monkeypatch, universe):
    monkeypatch.setattr(runner, "build_universe", lambda: universe)
    candles = [{"ts": i * 3_600_000, "close": 100 + i} for i in range(1, 10)]
    monkeypatch.setattr(runner, "get_history", lambda *args, **kwargs: candles)
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
    monkeypatch.setattr(runner, "score_shadow_signal_v3", lambda *args, **kwargs: {"families": []})


def test_run_counts_one_oi_acquisition_per_base_and_exposes_no_symbols(monkeypatch):
    _patch_minimal_run_dependencies(monkeypatch, [{"symbol": "BTC-USD", "base": "BTC"}])
    calls = []

    def fake_oi(base):
        calls.append(base)
        return runner._OIHistory([], source_status="network_error")

    monkeypatch.setattr(runner, "_oi_points", fake_oi)

    report = runner.run(persist=False)
    diagnostic = report["oi_source_diagnostics"]

    assert calls == ["BTC"]
    assert diagnostic["acquisition_attempts"] == 1
    assert diagnostic["status_counts"] == {"network_error": 1}
    assert diagnostic["extra_requests_added"] == 0
    assert diagnostic["symbol_level_data_exposed"] is False
    assert "BTC" not in repr(diagnostic)
    assert diagnostic["trade_authority"] is False
    assert diagnostic["promotion_authority"] is False


def test_run_opens_source_level_circuit_after_first_http_451(monkeypatch):
    _patch_minimal_run_dependencies(
        monkeypatch,
        [
            {"symbol": "BTC-USD", "base": "BTC"},
            {"symbol": "ETH-USD", "base": "ETH"},
            {"symbol": "SOL-USD", "base": "SOL"},
        ],
    )
    calls = []

    def fake_oi(base):
        calls.append(base)
        return runner._OIHistory([], source_status="http_451")

    monkeypatch.setattr(runner, "_oi_points", fake_oi)

    report = runner.run(persist=False)
    diagnostic = report["oi_source_diagnostics"]

    # 451 is a source/region restriction. One real attempt is enough for this cycle;
    # remaining bases fail closed without repeating the same blocked request.
    assert calls == ["BTC"]
    assert diagnostic["acquisition_attempts"] == 1
    assert diagnostic["status_counts"] == {"http_451": 1}
    assert diagnostic["extra_requests_added"] == 0
    assert diagnostic["trade_authority"] is False
    assert diagnostic["promotion_authority"] is False

    v3 = report["v3_oi_causal_asof_feature_availability"]["horizons"]
    for horizon in runner.V3_DIAGNOSTIC_HORIZONS:
        assert v3[horizon]["oi_unavailable_reason_counts"].get("oi_unavailable") == 3


def test_non_451_failures_do_not_open_source_level_circuit(monkeypatch):
    _patch_minimal_run_dependencies(
        monkeypatch,
        [
            {"symbol": "BTC-USD", "base": "BTC"},
            {"symbol": "ETH-USD", "base": "ETH"},
        ],
    )
    calls = []

    def fake_oi(base):
        calls.append(base)
        return runner._OIHistory([], source_status="timeout")

    monkeypatch.setattr(runner, "_oi_points", fake_oi)

    report = runner.run(persist=False)

    assert calls == ["BTC", "ETH"]
    assert report["oi_source_diagnostics"]["acquisition_attempts"] == 2
    assert report["oi_source_diagnostics"]["status_counts"] == {"timeout": 2}


def test_adaptive_boundary_reallowlists_only_fixed_oi_source_categories(monkeypatch):
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
            "oi_source_diagnostics": {
                "diagnostic_only": True,
                "source": "MUST_NOT_ESCAPE",
                "acquisition_attempts": 12,
                "status_counts": {"http_error": 11, "available": 1, "BTCUSDT": 999},
                "raw_error": "secret endpoint text",
            },
        },
    )

    bounded = adaptive_runner._ffrizz_forward_collection()["oi_source_diagnostics"]

    assert bounded["source"] == "binance_open_interest_history"
    assert bounded["acquisition_attempts"] == 12
    assert bounded["status_counts"] == {"available": 1, "http_error": 11}
    assert bounded["extra_requests_added"] == 0
    assert bounded["symbol_level_data_exposed"] is False
    assert "BTC" not in repr(bounded)
    assert "secret" not in repr(bounded)
    assert "MUST_NOT_ESCAPE" not in repr(bounded)

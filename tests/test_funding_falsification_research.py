import funding_falsification_research as ff
import funding_history_research as fh

H = 60 * 60 * 1000


def test_funding_history_uses_actual_timestamps_and_bounded_pagination(monkeypatch):
    calls = []

    def fake_okx(path, params=None):
        calls.append((path, dict(params or {})))
        if path == "/api/v5/public/funding-rate-history":
            if "after" not in params:
                return [
                    {"fundingTime": str(30 * H), "realizedRate": "0.0003"},
                    {"fundingTime": str(22 * H), "realizedRate": "0.0002"},
                ]
            return [
                {"fundingTime": str(14 * H), "realizedRate": "0.0001"},
                {"fundingTime": str(5 * H), "realizedRate": "-0.0001"},
            ]
        if path == "/api/v5/market/history-index-candles":
            return [[i * H, "100", "100", "100", str(100 + i), "1"] for i in range(50, 0, -1)]
        raise AssertionError(path)

    monkeypatch.setattr(fh, "okx_get", fake_okx)
    monkeypatch.setattr("basis_history_research.okx_get", fake_okx)
    result = fh.collect_okx_funding_history(
        "btc", funding_target_points=4, index_target_points=20,
        funding_max_pages=2, index_max_pages=1,
    )
    assert result["available"] is True
    assert [p["ts"] for p in result["funding_points"]] == [5 * H, 14 * H, 22 * H, 30 * H]
    assert result["uses_actual_funding_timestamps"] is True
    assert result["assumed_fixed_funding_interval"] is False
    funding_calls = [c for c in calls if c[0] == "/api/v5/public/funding-rate-history"]
    assert len(funding_calls) == 2
    assert funding_calls[1][1]["after"] == str(22 * H)


def _dataset(hours=1200):
    index = []
    for i in range(hours + 1):
        # Persistent drift gives the training-only constant-direction baseline a
        # real hurdle while alternating funding pressure supplies independent
        # variation for the frozen feature.
        index.append({"ts": i * H, "value": 100.0 + 0.02 * i})
    funding = []
    for i in range(8, hours, 8):
        cycle = (i // 8) % 4
        rate = 0.0004 if cycle in (0, 1) else -0.0004
        funding.append({"ts": i * H, "value": rate})
    return {
        "research_only": True,
        "candidate_id": "DATA-FUNDING-001",
        "available": True,
        "funding_points": funding,
        "index_points": index,
    }


def test_causal_examples_never_use_future_funding():
    dataset = {
        "funding_points": [
            {"ts": 1 * H, "value": 0.001},
            {"ts": 25 * H, "value": 0.009},
        ],
        "index_points": [
            {"ts": 24 * H, "value": 100.0},
            {"ts": 48 * H, "value": 101.0},
        ],
    }
    rows = ff._causal_examples(dataset, 24)
    assert len(rows) == 1
    assert rows[0]["forecast_ts"] == 24 * H
    assert rows[0]["funding_pressure_bps"] == 10.0
    assert rows[0]["funding_observations"] == 1


def test_funding_horizon_fails_closed_below_oos_floor():
    result = ff.evaluate_funding_horizon(_dataset(hours=240), 24, min_oos_samples=8)
    assert result["available"] is False
    assert result["reason"] == "insufficient_oos_samples_before_scoring"


def test_funding_evaluation_reports_cost_stress_baseline_and_no_authority():
    result = ff.evaluate_funding_horizon(_dataset(), 24, cost_bps=12, min_oos_samples=8)
    assert result["available"] is True
    assert result["causal_realized_funding_only"] is True
    assert result["threshold_tuning"] is False
    assert set(result["cost_stress"]) == {"1x", "2x", "3x"}
    assert result["cost_stress"]["3x"]["cost_bps_round_trip"] == 36.0
    assert "incremental_after_cost_vs_baseline_positive" in result
    assert len(result["oos_half_avg_net_bps"]) == 2
    assert result["promotion_authority"] is False
    assert result["production_authority"] is False

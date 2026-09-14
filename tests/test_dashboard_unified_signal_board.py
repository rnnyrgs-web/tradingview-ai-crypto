import dashboard


def test_unified_board_uses_internal_horizons_without_exposing_bucket_choice(monkeypatch):
    rows_by_horizon = {
        "6h": [
            {
                "id": 1,
                "symbol": "BTCUSDT",
                "action": "WAIT",
                "direction": "LONG",
                "timeframe": "6h",
                "entry_price": 100.0,
                "target_2": 104.0,
                "evidence_score": 90.0,
                "calibration": {"ready": False, "independent_samples": 8, "minimum_samples": 30},
            }
        ],
        "24h": [
            {
                "id": 2,
                "symbol": "BTCUSDT",
                "action": "TRADE",
                "direction": "LONG",
                "timeframe": "24h",
                "entry_price": 100.0,
                "target_2": 110.0,
                "evidence_score": 70.0,
                "calibration": {
                    "ready": True,
                    "independent_samples": 35,
                    "minimum_samples": 30,
                    "empirical_precision": 0.71,
                    "precision_95pct_lower": 0.60,
                },
            }
        ],
    }

    monkeypatch.setattr(dashboard, "PERSISTED_SIGNAL_HORIZONS", ("6h", "24h"))
    monkeypatch.setattr(
        dashboard,
        "fetch_ranked_opportunities",
        lambda *, horizon, limit: rows_by_horizon.get(horizon, []),
    )

    rows = dashboard._rows_for_dashboard(limit_per_horizon=20)

    assert len(rows) == 1
    assert rows[0]["id"] == 2
    assert dashboard._trade_label(rows[0]) == "LONG"
    assert dashboard._estimated_duration(rows[0]) == "12–24 hours"


def test_calibration_never_publishes_unready_precision():
    metrics = dashboard._calibration_metrics(
        {
            "calibration": {
                "ready": False,
                "independent_samples": 12,
                "minimum_samples": 30,
                "empirical_precision": 0.99,
                "precision_95pct_lower": 0.95,
            }
        }
    )

    assert metrics["accuracy"] == "LEARNING"
    assert metrics["precision"] is None
    assert metrics["floor"] == "—"
    assert metrics["n"] == "N=12/30"


def test_trade_labels_and_move_duration_are_directional_and_horizon_derived():
    assert dashboard._trade_label({"action": "WAIT", "direction": "LONG"}) == "WAIT"
    assert dashboard._trade_label({"action": "TRADE", "direction": "LONG"}) == "LONG"
    assert dashboard._trade_label({"action": "TRADE", "direction": "SHORT"}) == "SHORT"
    assert dashboard._estimated_duration({"timeframe": "7d"}) == "3–7 days"
    assert dashboard._move_multiple(100.0) == "~2.00×"

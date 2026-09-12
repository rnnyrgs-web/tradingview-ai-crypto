from basis_observability import compact_basis_falsification
import continuous_coordinator as coordinator


def _army_with_funding_evidence():
    return {
        "workers": {
            "basis-falsification-btc": {
                "last_exit_code": 0,
                "elapsed_seconds": 12.5,
                "last_finished_at": "2026-09-12T04:30:00+00:00",
                "latest_evidence": {
                    "task_id": "COORD-DATA-004",
                    "candidate_id": "DATA-FUNDING-001",
                    "base": "BTC",
                    "evidence_conclusion": "stage1_evaluated",
                    "available_primary_results": 2,
                    "stage1_pass_count": 1,
                    "collection": {
                        "available": True,
                        "reason": None,
                        "funding_point_count": 1200,
                        "index_point_count": 5000,
                        "funding_pages": 12,
                        "index_pages": 50,
                        "uses_actual_funding_timestamps": True,
                        "assumed_fixed_funding_interval": False,
                        "completed_price_candles_only": True,
                        "interpolation_allowed": False,
                        "forward_fill_allowed": False,
                        "nearest_neighbor_matching": False,
                        "raw_rows": [{"secret": "must-not-leak"}],
                    },
                    "results": {
                        "24": {
                            "available": True,
                            "horizon_hours": 24,
                            "chronological_split": "60_percent_train_40_percent_oos",
                            "non_overlapping": True,
                            "causal_realized_funding_only": True,
                            "feature_window_hours": 24,
                            "assumed_fixed_funding_interval": False,
                            "training_only_direction": -1,
                            "training_only_baseline_direction": 1,
                            "threshold_tuning": False,
                            "sample_count": 100,
                            "train_samples": 60,
                            "oos_samples": 40,
                            "minimum_oos_samples": 8,
                            "oos_directional_hit_rate": 0.625,
                            "cost_stress": {
                                "1x": {"cost_bps_round_trip": 12.0, "avg_net_bps": 19.0, "baseline_avg_net_bps": 5.0, "incremental_vs_baseline_bps": 14.0, "positive_after_cost": True},
                                "2x": {"cost_bps_round_trip": 24.0, "avg_net_bps": 7.0, "baseline_avg_net_bps": -7.0, "incremental_vs_baseline_bps": 14.0, "positive_after_cost": True},
                                "3x": {"cost_bps_round_trip": 36.0, "avg_net_bps": -5.0, "baseline_avg_net_bps": -19.0, "incremental_vs_baseline_bps": 14.0, "positive_after_cost": False},
                            },
                            "oos_half_avg_net_bps": [20.0, 18.0],
                            "stable_positive_oos_halves": True,
                            "survives_3x_cost_stress": False,
                            "incremental_after_cost_vs_baseline_positive": True,
                            "stage1_pass": False,
                            "forecast_rows": [{"secret": "must-not-leak"}],
                            "promotion_authority": True,
                        },
                        "168": {"available": False, "reason": "insufficient_oos_samples_before_scoring", "sample_count": 18, "train_samples": 10, "oos_samples": 8, "minimum_oos_samples": 8},
                        "evil": {"raw": "must-not-leak"},
                    },
                    "arbitrary_payload": "must-not-leak",
                    "promotion_authority": True,
                },
            }
        },
        "observability": {},
        "supervisor": {},
    }


def test_projection_exposes_only_funding_profitability_allowlist():
    result = compact_basis_falsification(_army_with_funding_evidence())

    assert result["task_id"] == "COORD-DATA-004"
    assert result["candidate_id"] == "DATA-FUNDING-001"
    assert result["legacy_observability_key"] == "basis_falsification"
    assert result["available_primary_results"] == 2
    assert result["stage1_pass_count"] == 1
    assert result["collection"]["funding_point_count"] == 1200
    assert result["collection"]["uses_actual_funding_timestamps"] is True
    assert result["results"]["24"]["oos_directional_hit_rate"] == 0.625
    assert result["results"]["24"]["cost_stress"]["1x"]["avg_net_bps"] == 19.0
    assert result["results"]["24"]["stage1_pass"] is False
    assert result["results"]["24"]["promotion_authority"] is False
    assert set(result["results"]) == {"24", "168"}
    assert "raw_rows" not in result["collection"]
    assert "forecast_rows" not in result["results"]["24"]
    assert "arbitrary_payload" not in result
    assert result["production_authority"] is False
    assert result["signal_authority"] is False
    assert result["paper_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_authority"] is False


def test_projection_does_not_reinterpret_rejected_basis_evidence_as_funding():
    army = _army_with_funding_evidence()
    army["workers"]["basis-falsification-btc"]["latest_evidence"]["candidate_id"] = "DATA-BASIS-001"
    army["workers"]["basis-falsification-btc"]["latest_evidence"]["task_id"] = "COORD-DATA-003"
    result = compact_basis_falsification(army)
    assert result["candidate_id"] == "DATA-FUNDING-001"
    assert result["evidence_conclusion"] is None
    assert result["available_primary_results"] is None
    assert result["collection"]["available"] is False
    assert result["results"]["24"] is None


def test_coordinator_log_payload_includes_bounded_funding_projection():
    army = _army_with_funding_evidence()
    payload = coordinator.observability_log_payload(army)

    assert payload["basis_falsification"] == compact_basis_falsification(army)
    assert payload["basis_falsification"]["candidate_id"] == "DATA-FUNDING-001"
    assert payload["basis_falsification"]["results"]["24"]["cost_stress"]["1x"]["avg_net_bps"] == 19.0
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["signal_authority"] is False

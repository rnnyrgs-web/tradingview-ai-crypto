from basis_observability import compact_basis_falsification
import continuous_coordinator as coordinator


def _army_with_basis_evidence():
    return {
        "workers": {
            "basis-falsification-btc": {
                "last_exit_code": 0,
                "elapsed_seconds": 12.5,
                "last_finished_at": "2026-09-11T18:00:00+00:00",
                "latest_evidence": {
                    "task_id": "COORD-DATA-003",
                    "candidate_id": "DATA-BASIS-001",
                    "base": "BTC",
                    "evidence_conclusion": "stage1_evaluated",
                    "available_primary_results": 2,
                    "collection": {
                        "available": True,
                        "reason": None,
                        "target_points": 4000,
                        "point_count": 4000,
                        "mark_point_count": 4000,
                        "index_point_count": 4000,
                        "mark_pages": 40,
                        "index_pages": 40,
                        "alignment": "exact_shared_timestamp_only",
                        "completed_candles_only": True,
                        "interpolation_allowed": False,
                        "raw_rows": [{"secret": "must-not-leak"}],
                    },
                    "results": {
                        "24": {
                            "available": True,
                            "horizon_hours": 24,
                            "chronological": True,
                            "non_overlapping": True,
                            "exact_timestamp_labels": True,
                            "training_only_direction": -1,
                            "threshold_tuning": False,
                            "sample_count": 120,
                            "train_samples": 72,
                            "oos_samples": 48,
                            "minimum_oos_samples": 8,
                            "cost_bps_round_trip": 12.0,
                            "oos_directional_hit_rate": 0.625,
                            "oos_avg_gross_bps": 31.0,
                            "oos_avg_net_bps": 19.0,
                            "oos_sum_net_bps": 912.0,
                            "positive_after_cost_oos": True,
                            "forecast_rows": [{"secret": "must-not-leak"}],
                            "promotion_authority": True,
                        },
                        "168": {
                            "available": False,
                            "reason": "insufficient_oos_samples_before_scoring",
                            "sample_count": 18,
                            "train_samples": 10,
                            "oos_samples": 8,
                            "minimum_oos_samples": 8,
                        },
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


def test_basis_projection_exposes_only_profitability_relevant_allowlist():
    result = compact_basis_falsification(_army_with_basis_evidence())

    assert result["task_id"] == "COORD-DATA-003"
    assert result["candidate_id"] == "DATA-BASIS-001"
    assert result["available_primary_results"] == 2
    assert result["collection"]["point_count"] == 4000
    assert result["collection"]["alignment"] == "exact_shared_timestamp_only"
    assert result["results"]["24"]["oos_directional_hit_rate"] == 0.625
    assert result["results"]["24"]["oos_avg_net_bps"] == 19.0
    assert result["results"]["24"]["positive_after_cost_oos"] is True
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


def test_coordinator_log_payload_includes_bounded_basis_projection():
    army = _army_with_basis_evidence()
    payload = coordinator.observability_log_payload(army)

    assert payload["basis_falsification"] == compact_basis_falsification(army)
    assert payload["basis_falsification"]["results"]["24"]["oos_avg_net_bps"] == 19.0
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["signal_authority"] is False

import continuous_coordinator as coordinator


def _army(v2):
    return {
        "observability": {
            "adaptive_accuracy": {
                "latest_evidence": {
                    "ffrizz_forward_collection": {
                        "ok": True,
                        "eligible_shadow_forecasts": 0,
                        "v2_oi_alignment_feature_availability": v2,
                    }
                }
            }
        }
    }


def test_v2_feature_availability_reaches_logs_with_strict_allowlist():
    raw = {
        "system": "untrusted-input-name",
        "diagnostic_only": True,
        "symbol_level_data_exposed": True,
        "horizons": {
            "6h": {
                "signals_scored": 12,
                "family_counts": {
                    "pb_ema:available": 12,
                    "price_oi_correlation_v2:available": 9,
                    "price_oi_correlation_v2:unavailable": 3,
                    "secret_family": 999,
                },
                "symbols": ["must-not-leak"],
            },
            "12h": {
                "signals_scored": 12,
                "family_counts": {"price_oi_correlation_v2:available": 8},
            },
            "24h": {
                "signals_scored": 12,
                "family_counts": {"price_oi_correlation_v2:unavailable": 4},
            },
            "48h": {
                "signals_scored": 12,
                "family_counts": {"price_oi_correlation_v2:available": 12},
            },
        },
        "raw_rows": [{"symbol": "must-not-leak"}],
        "trade_authority": True,
        "promotion_authority": True,
    }

    value = coordinator.observability_log_payload(_army(raw))["ffrizz_forward"][
        "v2_oi_alignment_feature_availability"
    ]

    assert value == {
        "system": "FFRIZZ_SECONDARY_V2_OI_CLOSE_END",
        "diagnostic_only": True,
        "symbol_level_data_exposed": False,
        "horizons": {
            "6h": {
                "signals_scored": 12,
                "family_counts": {
                    "pb_ema:available": 12,
                    "price_oi_correlation_v2:available": 9,
                    "price_oi_correlation_v2:unavailable": 3,
                },
            },
            "12h": {
                "signals_scored": 12,
                "family_counts": {"price_oi_correlation_v2:available": 8},
            },
            "24h": {
                "signals_scored": 12,
                "family_counts": {"price_oi_correlation_v2:unavailable": 4},
            },
        },
        "trade_authority": False,
        "promotion_authority": False,
    }
    serialized = str(value)
    assert "48h" not in serialized
    assert "secret_family" not in serialized
    assert "must-not-leak" not in serialized
    assert "raw_rows" not in serialized


def test_v2_feature_availability_rejects_malformed_counts_and_missing_payload():
    malformed = {
        "diagnostic_only": False,
        "horizons": {
            "6h": {
                "signals_scored": "12",
                "family_counts": {
                    "price_oi_correlation_v2:available": True,
                    "price_oi_correlation_v2:unavailable": -1,
                    "fvg:available": 7,
                },
            }
        },
    }
    value = coordinator.observability_log_payload(_army(malformed))["ffrizz_forward"][
        "v2_oi_alignment_feature_availability"
    ]
    assert value["diagnostic_only"] is False
    assert value["horizons"]["6h"] == {
        "signals_scored": None,
        "family_counts": {"fvg:available": 7},
    }
    assert coordinator.observability_log_payload(_army(None))["ffrizz_forward"][
        "v2_oi_alignment_feature_availability"
    ] is None

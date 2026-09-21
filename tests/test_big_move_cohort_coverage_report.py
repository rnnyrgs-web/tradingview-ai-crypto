from copy import deepcopy

import pytest

from big_move_cohort_coverage_report import build_blocker_report


CONTRACT = {
    "required_features": [
        "price",
        "liquidity_usd",
        "market_cap_usd",
        "float_supply",
        "listing_age_days",
        "volatility_30d",
        "return_30d",
        "sector",
        "regime",
        "tradable",
        "member",
    ],
    "coverage_thresholds": {
        "minimum_assets": 12,
        "minimum_snapshots": 624,
        "minimum_decisions_per_asset": 52,
    },
}


def _coverage():
    return {
        "schema": "two_x_cohort_coverage_result.v1",
        "status": "COVERAGE_BLOCKED",
        "contract_digest": "a" * 64,
        "result_digest": "b" * 64,
        "accepted_snapshot_count": 40,
        "eligible_snapshot_count": 0,
        "excluded_snapshot_count": 3,
        "eligible_asset_count": 0,
        "eligible_assets": [],
        "per_asset_snapshot_counts": {"btc": 40},
        "duplicate_snapshot_key_count": 1,
        "exclusions": [
            {"index": 0, "stable_asset_id": "btc", "reasons": ["identity evidence missing"]},
            {"index": 1, "stable_asset_id": "eth", "reasons": ["float_supply source proof missing"]},
            {
                "index": 2,
                "stable_asset_id": "sol",
                "reasons": ["duplicate stable_asset_id/venue/decision_at snapshot is ambiguous and cannot count toward coverage"],
            },
        ],
        "outcome_access": "SEALED",
        "forward_formation_status": "BLOCKED_UNTIL_TRUSTED_RECEIPT",
        "prediction_authority": False,
        "trade_authority": False,
        "broker_connected": False,
    }


def test_blocked_report_quantifies_shortfalls_without_opening_outcomes():
    report = build_blocker_report(CONTRACT, _coverage())
    assert report["coverage_status"] == "COVERAGE_BLOCKED"
    assert report["threshold_shortfalls"]["assets_needed"] == 12
    assert report["threshold_shortfalls"]["eligible_snapshots_needed"] == 624
    assert report["threshold_shortfalls"]["asset_decision_shortfalls"] == {"btc": 12}
    assert report["blocker_counts_by_feature"]["identity"] == 1
    assert report["blocker_counts_by_feature"]["float_supply"] == 1
    assert report["next_data_build_priority"] == "stable_identity"
    assert report["scientific_rules"]["outcomes_opened"] is False
    assert report["scientific_rules"]["thresholds_weakened"] is False
    assert report["outcome_access"] == "SEALED_IN_THIS_REPORTER"
    assert report["prediction_authority"] is False
    assert report["trade_authority"] is False
    assert report["broker_connected"] is False
    assert len(report["report_digest"]) == 64


def test_report_is_deterministic():
    first = build_blocker_report(CONTRACT, _coverage())
    second = build_blocker_report(deepcopy(CONTRACT), deepcopy(_coverage()))
    assert first == second


def test_ready_result_never_opens_labels_inside_reporter():
    coverage = _coverage()
    coverage.update(
        status="READY_FOR_LABEL_OPEN",
        eligible_asset_count=12,
        eligible_snapshot_count=624,
        per_asset_snapshot_counts={f"asset-{i}": 52 for i in range(12)},
        exclusions=[],
        excluded_snapshot_count=0,
        duplicate_snapshot_key_count=0,
    )
    report = build_blocker_report(CONTRACT, coverage)
    assert report["next_data_build_priority"] == "LABEL_STAGE_HANDOFF_ONLY_NO_OUTCOME_OPEN_IN_REPORTER"
    assert report["threshold_shortfalls"]["assets_needed"] == 0
    assert report["threshold_shortfalls"]["eligible_snapshots_needed"] == 0
    assert report["outcome_access"] == "SEALED_IN_THIS_REPORTER"


@pytest.mark.parametrize(
    "field,value",
    [
        ("prediction_authority", True),
        ("trade_authority", True),
        ("broker_connected", True),
    ],
)
def test_report_refuses_authority_bearing_coverage_results(field, value):
    coverage = _coverage()
    coverage[field] = value
    with pytest.raises(ValueError):
        build_blocker_report(CONTRACT, coverage)


def test_report_refuses_malformed_exclusion_reasons():
    coverage = _coverage()
    coverage["exclusions"][0]["reasons"] = "identity evidence missing"
    with pytest.raises(ValueError):
        build_blocker_report(CONTRACT, coverage)

import hashlib
import json
from pathlib import Path

import pytest

from big_move_cohort_preflight import evaluate_coverage, validate_contract


def _contract():
    return {
        "schema": "two_x_cohort_preflight.v1",
        "frozen_at": "2026-09-21T04:40:00Z",
        "outcome_access": "SEALED_UNTIL_COVERAGE_READY",
        "forward_formation_status": "BLOCKED_UNTIL_TRUSTED_RECEIPT",
        "historical_universe_rule": {
            "venue": "BINANCE_SPOT",
            "quote_asset": "USDT",
            "decision_grid": "MONDAY_00_UTC_WEEKLY",
            "grid_start": "2021-01-04T00:00:00Z",
            "grid_end": "2026-06-29T00:00:00Z",
            "listing_age_min_days": 180,
            "trailing_30d_median_quote_volume_usd_min": 10_000_000,
        },
        "coverage_thresholds": {
            "minimum_assets": 2,
            "minimum_snapshots": 4,
            "minimum_decisions_per_asset": 2,
        },
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
        "feature_kinds": {
            "price": "positive_number",
            "liquidity_usd": "positive_number",
            "market_cap_usd": "positive_number",
            "float_supply": "positive_number",
            "listing_age_days": "nonnegative_number",
            "volatility_30d": "nonnegative_number",
            "return_30d": "finite_number",
            "sector": "nonempty_string",
            "regime": "nonempty_string",
            "tradable": "bool",
            "member": "bool",
        },
        "identity_source_eligibility": ["IDENTITY"],
        "source_eligibility": {
            "price": ["PRICE"],
            "liquidity_usd": ["LIQUIDITY"],
            "market_cap_usd": ["MARKET_CAP"],
            "float_supply": ["SUPPLY"],
            "listing_age_days": ["LISTING"],
            "volatility_30d": ["DERIVED"],
            "return_30d": ["DERIVED"],
            "sector": ["SECTOR"],
            "regime": ["REGIME"],
            "tradable": ["MEMBERSHIP"],
            "member": ["MEMBERSHIP"],
        },
    }


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _evidence(source_id, value, available_at):
    return {
        "source_id": source_id,
        "source_version": "v1",
        "raw_digest_sha256": _sha(f"{source_id}-{available_at}-{value}"),
        "observed_at": available_at,
        "available_at": available_at,
        "value": value,
    }


def _snapshot(asset, decision_at):
    return {
        "stable_asset_id": asset,
        "venue": "BINANCE_SPOT",
        "venue_symbol": f"{asset.upper()}USDT",
        "decision_at": decision_at,
        "identity": {
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_to": None,
            "evidence": _evidence(
                "IDENTITY", f"{asset}-identity", "2020-01-01T00:00:00Z"
            ),
        },
        "features": {
            "price": _evidence("PRICE", 10, decision_at),
            "liquidity_usd": _evidence("LIQUIDITY", 50_000_000, decision_at),
            "market_cap_usd": _evidence("MARKET_CAP", 1_000_000_000, decision_at),
            "float_supply": _evidence("SUPPLY", 100_000_000, decision_at),
            "listing_age_days": _evidence("LISTING", 500, decision_at),
            "volatility_30d": _evidence("DERIVED", 0.6, decision_at),
            "return_30d": _evidence("DERIVED", -0.1, decision_at),
            "sector": _evidence("SECTOR", "L1", decision_at),
            "regime": _evidence("REGIME", "RISK_ON", decision_at),
            "tradable": _evidence("MEMBERSHIP", True, decision_at),
            "member": _evidence("MEMBERSHIP", True, decision_at),
        },
    }


def test_ready_only_after_predeclared_coverage_thresholds():
    contract = _contract()
    rows = [
        _snapshot("a", "2024-01-01T00:00:00Z"),
        _snapshot("a", "2024-01-08T00:00:00Z"),
        _snapshot("b", "2024-01-01T00:00:00Z"),
        _snapshot("b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows)
    assert result["status"] == "READY_FOR_LABEL_OPEN"
    assert result["eligible_asset_count"] == 2
    assert result["eligible_snapshot_count"] == 4
    assert result["duplicate_snapshot_key_count"] == 0
    assert result["forward_formation_status"] == "BLOCKED_UNTIL_TRUSTED_RECEIPT"
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False


def test_late_or_unapproved_feature_blocks_snapshot():
    contract = _contract()
    row = _snapshot("a", "2024-01-01T00:00:00Z")
    row["features"]["float_supply"]["available_at"] = "2024-01-02T00:00:00Z"
    row["features"]["sector"]["source_id"] = "CURRENT_CATEGORY_TAG"
    result = evaluate_coverage(contract, [row])
    assert result["status"] == "COVERAGE_BLOCKED"
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert "float_supply was not available by decision_at" in reasons
    assert "sector.source_id is not approved" in reasons


@pytest.mark.parametrize(
    "key", ["outcome", "reached_2x", "future_return", "target_hit_at"]
)
def test_outcome_leakage_is_rejected_before_label_open(key):
    contract = _contract()
    row = _snapshot("a", "2024-01-01T00:00:00Z")
    row["research"] = {key: "leak"}
    with pytest.raises(ValueError, match="outcome-derived key forbidden"):
        evaluate_coverage(contract, [row])


def test_sparse_asset_does_not_count_toward_minimum():
    contract = _contract()
    rows = [
        _snapshot("a", "2024-01-01T00:00:00Z"),
        _snapshot("a", "2024-01-08T00:00:00Z"),
        _snapshot("b", "2024-01-01T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows)
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["eligible_assets"] == ["a"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("wrong_venue", "venue does not match frozen historical universe"),
        ("off_grid", "decision_at is not on MONDAY_00_UTC_WEEKLY grid"),
        ("before_grid", "decision_at lies outside frozen grid range"),
        ("young_listing", "listing_age_days below frozen minimum"),
        ("thin_liquidity", "liquidity_usd below frozen minimum"),
        ("not_tradable", "tradable must be true at decision_at"),
        ("not_member", "member must be true at decision_at"),
    ],
)
def test_frozen_universe_gates_are_enforced(mutation, expected):
    contract = _contract()
    row = _snapshot("a", "2024-01-01T00:00:00Z")
    if mutation == "wrong_venue":
        row["venue"] = "OTHER"
    elif mutation == "off_grid":
        row = _snapshot("a", "2024-01-02T00:00:00Z")
    elif mutation == "before_grid":
        row = _snapshot("a", "2020-12-28T00:00:00Z")
    elif mutation == "young_listing":
        row["features"]["listing_age_days"]["value"] = 179
    elif mutation == "thin_liquidity":
        row["features"]["liquidity_usd"]["value"] = 9_999_999
    elif mutation == "not_tradable":
        row["features"]["tradable"]["value"] = False
    else:
        row["features"]["member"]["value"] = False

    result = evaluate_coverage(contract, [row])
    assert result["status"] == "COVERAGE_BLOCKED"
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert expected in reasons


def test_duplicate_decision_rows_cannot_inflate_coverage():
    contract = _contract()
    duplicate = _snapshot("a", "2024-01-01T00:00:00Z")
    rows = [
        duplicate,
        json.loads(json.dumps(duplicate)),
        _snapshot("a", "2024-01-08T00:00:00Z"),
        _snapshot("b", "2024-01-01T00:00:00Z"),
        _snapshot("b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows)
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["duplicate_snapshot_key_count"] == 1
    assert result["per_asset_snapshot_counts"] == {"a": 1, "b": 2}
    duplicate_exclusions = [
        row for row in result["exclusions"] if "duplicate" in " ".join(row["reasons"])
    ]
    assert len(duplicate_exclusions) == 2


def test_contract_rejects_unfrozen_or_invalid_historical_grid():
    contract = _contract()
    contract["historical_universe_rule"]["decision_grid"] = "DAILY"
    with pytest.raises(ValueError, match="MONDAY_00_UTC_WEEKLY"):
        validate_contract(contract)


def test_actual_frozen_contract_is_fail_closed_without_coverage():
    root = Path(__file__).parents[1]
    contract = json.loads(
        (root / "money_intelligence/2x_cohort_001_preflight_contract.json").read_text()
    )
    validate_contract(contract)
    result = evaluate_coverage(contract, [])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["outcome_access"] == "SEALED"
    assert result["forward_formation_status"] == "BLOCKED_UNTIL_TRUSTED_RECEIPT"
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False

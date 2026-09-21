import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from big_move_cohort_preflight import evaluate_coverage, validate_contract

UTC = timezone.utc


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
            "liquidity_usd": ["TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1"],
            "market_cap_usd": ["MARKET_CAP"],
            "float_supply": ["SUPPLY"],
            "listing_age_days": ["DERIVED_BINANCE_LISTING_AGE_DAYS_V1"],
            "volatility_30d": ["DERIVED_PRE_CUTOFF_VENUE_BARS_V1"],
            "return_30d": ["DERIVED_PRE_CUTOFF_VENUE_BARS_V1"],
            "sector": ["SECTOR"],
            "regime": ["DERIVED_BTC_MARKET_REGIME_V1"],
            "tradable": ["DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1"],
            "member": ["DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1"],
        },
    }


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _write_json(root, name, value):
    raw = _json_bytes(value)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "artifact_relpath": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _direct(root, name, source_id, value, at, derivation=None):
    artifact = {
        "source_id": source_id,
        "source_version": "v1",
        "observed_at": at,
        "available_at": at,
        "value": value,
    }
    if derivation is not None:
        artifact["derivation"] = derivation
    stored = _write_json(root, name, artifact)
    record = dict(artifact)
    record["raw_digest_sha256"] = stored["sha256"]
    record["artifact_relpath"] = stored["artifact_relpath"]
    return record


def _liquidity(root, prefix, decision_at, value=50_000_000, days=30):
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    rows = []
    for offset in range(days, 0, -1):
        rows.append(
            {
                "date": (decision.date() - timedelta(days=offset)).isoformat(),
                "quote_volume_usd": value,
            }
        )
    inp = _write_json(
        root,
        f"{prefix}/liquidity_input.json",
        {"schema": "binance_daily_quote_volume.v1", "rows": rows},
    )
    derivation = {
        "transform_id": "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1",
        "transform_version": "1",
        "parameters": {
            "window_days": 30,
            "statistic": "median",
            "measure": "quote_volume_usd",
            "completed_daily_bars_only": True,
        },
        "inputs": [inp],
    }
    return _direct(
        root,
        f"{prefix}/liquidity_evidence.json",
        "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1",
        value,
        decision_at,
        derivation,
    )


def _listing_age(root, prefix, decision_at, days=500):
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    first = decision - timedelta(days=days)
    inp = _write_json(
        root,
        f"{prefix}/first_trade.json",
        {
            "schema": "binance_first_trade.v1",
            "first_trade_at": first.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        },
    )
    derivation = {
        "transform_id": "DERIVED_BINANCE_LISTING_AGE_DAYS_V1",
        "transform_version": "1",
        "parameters": {
            "basis": "first_verified_venue_trade",
            "rounding": "floor_elapsed_days",
        },
        "inputs": [inp],
    }
    return _direct(
        root,
        f"{prefix}/listing_age_evidence.json",
        "DERIVED_BINANCE_LISTING_AGE_DAYS_V1",
        days,
        decision_at,
        derivation,
    )


def _presence_pair(root, prefix, decision_at, member=True, tradable=True):
    inp = _write_json(
        root,
        f"{prefix}/market_presence.json",
        {
            "schema": "binance_market_presence.v1",
            "decision_at": decision_at,
            "member": member,
            "tradable": tradable,
        },
    )
    derivation = {
        "transform_id": "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
        "transform_version": "1",
        "parameters": {"rule": "verified_market_presence_at_decision"},
        "inputs": [inp],
    }
    return (
        _direct(
            root,
            f"{prefix}/member_evidence.json",
            "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
            member,
            decision_at,
            derivation,
        ),
        _direct(
            root,
            f"{prefix}/tradable_evidence.json",
            "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
            tradable,
            decision_at,
            derivation,
        ),
    )


def _generic_derived(root, prefix, decision_at, source_id, value, metric):
    inp = _write_json(
        root,
        f"{prefix}/{metric}_input.json",
        {"schema": "frozen_input.v1", "metric": metric, "rows": [1, 2, 3]},
    )
    derivation = {
        "transform_id": source_id,
        "transform_version": "1",
        "parameters": {"metric": metric, "window_days": 30},
        "inputs": [inp],
    }
    return _direct(
        root,
        f"{prefix}/{metric}_evidence.json",
        source_id,
        value,
        decision_at,
        derivation,
    )


def _snapshot(root, asset, decision_at, *, liquidity_days=30):
    prefix = f"{asset}-{decision_at[:10]}"
    member, tradable = _presence_pair(root, prefix, decision_at)
    return {
        "stable_asset_id": asset,
        "venue": "BINANCE_SPOT",
        "venue_symbol": f"{asset.upper()}USDT",
        "decision_at": decision_at,
        "identity": {
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_to": None,
            "evidence": _direct(
                root,
                f"{prefix}/identity.json",
                "IDENTITY",
                f"{asset}-identity",
                "2020-01-01T00:00:00Z",
            ),
        },
        "features": {
            "price": _direct(root, f"{prefix}/price.json", "PRICE", 10, decision_at),
            "liquidity_usd": _liquidity(
                root, prefix, decision_at, days=liquidity_days
            ),
            "market_cap_usd": _direct(
                root,
                f"{prefix}/market_cap.json",
                "MARKET_CAP",
                1_000_000_000,
                decision_at,
            ),
            "float_supply": _direct(
                root,
                f"{prefix}/supply.json",
                "SUPPLY",
                100_000_000,
                decision_at,
            ),
            "listing_age_days": _listing_age(root, prefix, decision_at),
            "volatility_30d": _generic_derived(
                root,
                prefix,
                decision_at,
                "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
                0.6,
                "volatility_30d",
            ),
            "return_30d": _generic_derived(
                root,
                prefix,
                decision_at,
                "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
                -0.1,
                "return_30d",
            ),
            "sector": _direct(
                root, f"{prefix}/sector.json", "SECTOR", "L1", decision_at
            ),
            "regime": _generic_derived(
                root,
                prefix,
                decision_at,
                "DERIVED_BTC_MARKET_REGIME_V1",
                "RISK_ON",
                "regime",
            ),
            "tradable": tradable,
            "member": member,
        },
    }


def test_ready_requires_verified_retained_artifacts_and_frozen_thresholds(tmp_path):
    contract = _contract()
    rows = [
        _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows, tmp_path)
    assert result["status"] == "READY_FOR_LABEL_OPEN"
    assert result["source_verification"] == "RETAINED_ARTIFACT_BYTES_VERIFIED"
    assert result["eligible_asset_count"] == 2
    assert result["eligible_snapshot_count"] == 4
    assert result["duplicate_snapshot_key_count"] == 0
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False


def test_structural_metadata_without_retained_bytes_can_never_open_labels(tmp_path):
    contract = _contract()
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    result = evaluate_coverage(contract, [row])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["source_verification"] == "UNAVAILABLE"
    assert "retained artifact root" in " ".join(result["exclusions"][0]["reasons"])


def test_forged_allowed_source_value_or_digest_cannot_open_labels(tmp_path):
    contract = _contract()
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    row["features"]["price"]["value"] = 999
    result = evaluate_coverage(contract, [row], tmp_path)
    assert result["status"] == "COVERAGE_BLOCKED"
    assert "does not match retained artifact" in " ".join(result["exclusions"][0]["reasons"])

    row = _snapshot(tmp_path, "c", "2024-01-01T00:00:00Z")
    row["features"]["price"]["raw_digest_sha256"] = "0" * 64
    result = evaluate_coverage(contract, [row], tmp_path)
    assert "SHA-256 mismatch" in " ".join(result["exclusions"][0]["reasons"])


def test_single_day_or_current_liquidity_cannot_satisfy_30d_median_gate(tmp_path):
    contract = _contract()
    row = _snapshot(
        tmp_path, "a", "2024-01-01T00:00:00Z", liquidity_days=1
    )
    result = evaluate_coverage(contract, [row], tmp_path)
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert "requires all 30 completed UTC daily quote-volume observations" in reasons


def test_late_or_unapproved_feature_blocks_snapshot(tmp_path):
    contract = _contract()
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    row["features"]["float_supply"]["available_at"] = "2024-01-02T00:00:00Z"
    row["features"]["sector"]["source_id"] = "CURRENT_CATEGORY_TAG"
    result = evaluate_coverage(contract, [row], tmp_path)
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert "float_supply was not available by decision_at" in reasons
    assert "sector.source_id is not approved" in reasons


@pytest.mark.parametrize(
    "key", ["outcome", "reached_2x", "future_return", "target_hit_at"]
)
def test_outcome_leakage_is_rejected_before_label_open(tmp_path, key):
    contract = _contract()
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    row["research"] = {key: "leak"}
    with pytest.raises(ValueError, match="outcome-derived key forbidden"):
        evaluate_coverage(contract, [row], tmp_path)


def test_sparse_asset_does_not_count_toward_minimum(tmp_path):
    contract = _contract()
    rows = [
        _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows, tmp_path)
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
def test_frozen_universe_gates_are_enforced(tmp_path, mutation, expected):
    contract = _contract()
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    if mutation == "wrong_venue":
        row["venue"] = "OTHER"
    elif mutation == "off_grid":
        row = _snapshot(tmp_path, "offgrid", "2024-01-02T00:00:00Z")
    elif mutation == "before_grid":
        row = _snapshot(tmp_path, "before", "2020-12-28T00:00:00Z")
    elif mutation == "young_listing":
        row["features"]["listing_age_days"]["value"] = 179
    elif mutation == "thin_liquidity":
        row["features"]["liquidity_usd"]["value"] = 9_999_999
    elif mutation == "not_tradable":
        row["features"]["tradable"]["value"] = False
    else:
        row["features"]["member"]["value"] = False

    result = evaluate_coverage(contract, [row], tmp_path)
    assert result["status"] == "COVERAGE_BLOCKED"
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert expected in reasons


def test_duplicate_decision_rows_cannot_inflate_coverage(tmp_path):
    contract = _contract()
    duplicate = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    rows = [
        duplicate,
        json.loads(json.dumps(duplicate)),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(contract, rows, tmp_path)
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["duplicate_snapshot_key_count"] == 1
    assert result["per_asset_snapshot_counts"] == {"a": 1, "b": 2}


def test_contract_rejects_raw_liquidity_or_unfrozen_grid():
    contract = _contract()
    contract["source_eligibility"]["liquidity_usd"] = ["LIQUIDITY"]
    with pytest.raises(ValueError, match="raw caller values are forbidden"):
        validate_contract(contract)

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

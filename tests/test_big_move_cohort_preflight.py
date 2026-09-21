import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from big_move_cohort_preflight import evaluate_coverage, validate_contract
from big_move_source_authenticity import verify_source_policy_pin

UTC = timezone.utc
BINANCE = "BINANCE_PUBLIC_DATA_SPOT_RAW"
CM_CAP = "COINMETRICS_COMMUNITY_CAP_MRKT_CUR_USD"
CM_SUPPLY = "COINMETRICS_COMMUNITY_SPLY_CUR"
PRIMARY = "PRIMARY_CONTRACT_OR_GENESIS_DOC"
SECTOR = "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1"


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
            "price", "liquidity_usd", "market_cap_usd", "float_supply",
            "listing_age_days", "volatility_30d", "return_30d", "sector",
            "regime", "tradable", "member",
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
        "identity_source_eligibility": [PRIMARY],
        "source_eligibility": {
            "price": [BINANCE],
            "liquidity_usd": ["TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1"],
            "market_cap_usd": [CM_CAP],
            "float_supply": [CM_SUPPLY],
            "listing_age_days": ["DERIVED_BINANCE_LISTING_AGE_DAYS_V1"],
            "volatility_30d": ["DERIVED_PRE_CUTOFF_VENUE_BARS_V1"],
            "return_30d": ["DERIVED_PRE_CUTOFF_VENUE_BARS_V1"],
            "sector": [SECTOR],
            "regime": ["DERIVED_BTC_MARKET_REGIME_V1"],
            "tradable": ["DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1"],
            "member": ["DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1"],
        },
    }


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _write_bytes(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _write_json(root, name, value):
    return _write_bytes(root, name, _json_bytes(value))


def _binance_proof(root, prefix, decision_at):
    archive = _write_bytes(root, f"{prefix}/raw.zip", b"synthetic-binance-archive-fixture")
    checksum_text = f"{archive['sha256']}  raw.zip\n".encode()
    checksum = _write_bytes(root, f"{prefix}/raw.zip.CHECKSUM", checksum_text)
    proof = {
        "schema": "binance_public_archive_proof.v1",
        "source_id": BINANCE,
        "upstream_locator": "https://data.binance.vision/data/spot/daily/trades/TEST/TEST.zip",
        "archive_relpath": archive["artifact_relpath"],
        "archive_sha256": archive["sha256"],
        "checksum_relpath": checksum["artifact_relpath"],
        "checksum_sha256": checksum["sha256"],
        "event_time_max": decision_at,
    }
    return _write_json(root, f"{prefix}/binance_source_proof.json", proof)


def _coinmetrics_proof(root, prefix, source_id, value, observed_at, *, status_time=None):
    metric = "CapMrktCurUSD" if source_id == CM_CAP else "SplyCur"
    proof = {
        "schema": "coinmetrics_provider_status_proof.v1",
        "source_id": source_id,
        "upstream_locator": "https://api.coinmetrics.io/v4/timeseries/asset-metrics",
        "asset": "testasset",
        "metric": metric,
        "frequency": "1d",
        "record_id": f"testasset:{metric}:{observed_at}",
        "status": "reviewed",
        "status_time": status_time or observed_at,
        "observed_at": observed_at,
        "value": value,
    }
    return _write_json(root, f"{prefix}/{metric}_source_proof.json", proof)


def _primary_proof(root, prefix, source_id, value, published_at):
    document = _write_bytes(root, f"{prefix}/primary_document.txt", b"immutable primary document fixture")
    proof = {
        "schema": "primary_document_proof.v1",
        "source_id": source_id,
        "upstream_locator": "https://example.org/primary/document",
        "published_at": published_at,
        "effective_at": published_at,
        "document_relpath": document["artifact_relpath"],
        "document_sha256": document["sha256"],
        "claim_value": value,
    }
    return _write_json(root, f"{prefix}/primary_source_proof.json", proof)


def _direct(root, name, source_id, value, at, *, proof=None, derivation=None):
    artifact = {
        "source_id": source_id,
        "source_version": "v1",
        "observed_at": at,
        "available_at": at,
        "value": value,
        "source_proof": proof,
    }
    if derivation is not None:
        artifact["derivation"] = derivation
    stored = _write_json(root, name, artifact)
    record = dict(artifact)
    record["raw_digest_sha256"] = stored["sha256"]
    record["artifact_relpath"] = stored["artifact_relpath"]
    return record


def _binance_input(root, name, payload, decision_at):
    prefix = str(Path(name).with_suffix(""))
    proof = _binance_proof(root, prefix + "-proof", decision_at)
    artifact = dict(payload)
    artifact["source_id"] = BINANCE
    artifact["source_proof"] = proof
    return _write_json(root, name, artifact)


def _liquidity(root, prefix, decision_at, value=50_000_000, days=30):
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    rows = [
        {
            "date": (decision.date() - timedelta(days=offset)).isoformat(),
            "quote_volume_usd": value,
        }
        for offset in range(days, 0, -1)
    ]
    inp = _binance_input(
        root,
        f"{prefix}/liquidity_input.json",
        {"schema": "binance_daily_quote_volume.v1", "rows": rows},
        decision_at,
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
        root, f"{prefix}/liquidity_evidence.json",
        "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1", value, decision_at,
        proof=None, derivation=derivation,
    )


def _listing_age(root, prefix, decision_at, days=500):
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    first = decision - timedelta(days=days)
    inp = _binance_input(
        root,
        f"{prefix}/first_trade.json",
        {
            "schema": "binance_first_trade.v1",
            "first_trade_at": first.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        },
        decision_at,
    )
    derivation = {
        "transform_id": "DERIVED_BINANCE_LISTING_AGE_DAYS_V1",
        "transform_version": "1",
        "parameters": {"basis": "first_verified_venue_trade", "rounding": "floor_elapsed_days"},
        "inputs": [inp],
    }
    return _direct(
        root, f"{prefix}/listing_age_evidence.json",
        "DERIVED_BINANCE_LISTING_AGE_DAYS_V1", days, decision_at,
        proof=None, derivation=derivation,
    )


def _presence_pair(root, prefix, decision_at, member=True, tradable=True):
    inp = _binance_input(
        root,
        f"{prefix}/market_presence.json",
        {
            "schema": "binance_market_presence.v1",
            "decision_at": decision_at,
            "member": member,
            "tradable": tradable,
        },
        decision_at,
    )
    derivation = {
        "transform_id": "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
        "transform_version": "1",
        "parameters": {"rule": "verified_market_presence_at_decision"},
        "inputs": [inp],
    }
    return (
        _direct(root, f"{prefix}/member_evidence.json", "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1", member, decision_at, proof=None, derivation=derivation),
        _direct(root, f"{prefix}/tradable_evidence.json", "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1", tradable, decision_at, proof=None, derivation=derivation),
    )


def _generic_derived(root, prefix, decision_at, source_id, value, metric):
    inp = _binance_input(
        root,
        f"{prefix}/{metric}_input.json",
        {"schema": "frozen_input.v1", "metric": metric, "rows": [1, 2, 3]},
        decision_at,
    )
    derivation = {
        "transform_id": source_id,
        "transform_version": "1",
        "parameters": {"metric": metric, "window_days": 30},
        "inputs": [inp],
    }
    return _direct(
        root, f"{prefix}/{metric}_evidence.json", source_id, value, decision_at,
        proof=None, derivation=derivation,
    )


def _sector(root, prefix, decision_at, value="L1"):
    proof = _primary_proof(root, f"{prefix}/sector-doc", PRIMARY, value, decision_at)
    inp_artifact = {
        "schema": "primary_functional_role_input.v1",
        "source_id": PRIMARY,
        "observed_at": decision_at,
        "value": value,
        "source_proof": proof,
    }
    inp = _write_json(root, f"{prefix}/sector_input.json", inp_artifact)
    derivation = {
        "transform_id": SECTOR,
        "transform_version": "1",
        "parameters": {"classifier": "functional_role", "ambiguous_policy": "exclude"},
        "inputs": [inp],
    }
    return _direct(
        root, f"{prefix}/sector.json", SECTOR, value, decision_at,
        proof=None, derivation=derivation,
    )


def _snapshot(root, asset, decision_at, *, liquidity_days=30):
    prefix = f"{asset}-{decision_at[:10]}"
    member, tradable = _presence_pair(root, prefix, decision_at)
    identity_value = f"{asset}-identity"
    identity_proof = _primary_proof(root, f"{prefix}/identity-doc", PRIMARY, identity_value, "2020-01-01T00:00:00Z")
    price_proof = _binance_proof(root, f"{prefix}/price-proof", decision_at)
    cap_value = 1_000_000_000
    supply_value = 100_000_000
    cap_proof = _coinmetrics_proof(root, f"{prefix}/cap", CM_CAP, cap_value, decision_at)
    supply_proof = _coinmetrics_proof(root, f"{prefix}/supply", CM_SUPPLY, supply_value, decision_at)
    return {
        "stable_asset_id": asset,
        "venue": "BINANCE_SPOT",
        "venue_symbol": f"{asset.upper()}USDT",
        "decision_at": decision_at,
        "identity": {
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_to": None,
            "evidence": _direct(
                root, f"{prefix}/identity.json", PRIMARY, identity_value,
                "2020-01-01T00:00:00Z", proof=identity_proof,
            ),
        },
        "features": {
            "price": _direct(root, f"{prefix}/price.json", BINANCE, 10, decision_at, proof=price_proof),
            "liquidity_usd": _liquidity(root, prefix, decision_at, days=liquidity_days),
            "market_cap_usd": _direct(root, f"{prefix}/market_cap.json", CM_CAP, cap_value, decision_at, proof=cap_proof),
            "float_supply": _direct(root, f"{prefix}/supply.json", CM_SUPPLY, supply_value, decision_at, proof=supply_proof),
            "listing_age_days": _listing_age(root, prefix, decision_at),
            "volatility_30d": _generic_derived(root, prefix, decision_at, "DERIVED_PRE_CUTOFF_VENUE_BARS_V1", 0.6, "volatility_30d"),
            "return_30d": _generic_derived(root, prefix, decision_at, "DERIVED_PRE_CUTOFF_VENUE_BARS_V1", -0.1, "return_30d"),
            "sector": _sector(root, prefix, decision_at),
            "regime": _generic_derived(root, prefix, decision_at, "DERIVED_BTC_MARKET_REGIME_V1", "RISK_ON", "regime"),
            "tradable": tradable,
            "member": member,
        },
    }


def _rewrite_evidence(root, record, mutate):
    path = root / record["artifact_relpath"]
    artifact = json.loads(path.read_text())
    mutate(artifact)
    raw = _json_bytes(artifact)
    path.write_bytes(raw)
    record.clear()
    record.update(artifact)
    record["artifact_relpath"] = str(path.relative_to(root))
    record["raw_digest_sha256"] = hashlib.sha256(raw).hexdigest()


def test_source_policy_is_pinned_to_merged_preflight():
    policy = verify_source_policy_pin()
    assert policy["artifact_id"] == "2X-SOURCE-PREFLIGHT-001-v1"


def test_ready_requires_source_native_proof_and_frozen_thresholds(tmp_path):
    rows = [
        _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(_contract(), rows, tmp_path)
    assert result["status"] == "READY_FOR_LABEL_OPEN"
    assert result["source_verification"] == "SOURCE_NATIVE_AND_RETAINED_BYTES_VERIFIED"
    assert result["eligible_asset_count"] == 2
    assert result["eligible_snapshot_count"] == 4
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False


def test_self_consistent_backdated_supply_without_provider_proof_stays_blocked(tmp_path):
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    supply = row["features"]["float_supply"]
    _rewrite_evidence(tmp_path, supply, lambda artifact: artifact.__setitem__("source_proof", None))
    result = evaluate_coverage(_contract(), [row], tmp_path)
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert "source_proof missing" in reasons


def test_provider_native_status_time_after_cutoff_blocks_even_when_bytes_match(tmp_path):
    decision = "2024-01-01T00:00:00Z"
    row = _snapshot(tmp_path, "a", decision)
    supply = row["features"]["float_supply"]
    late_proof = _coinmetrics_proof(
        tmp_path, "late-proof", CM_SUPPLY, supply["value"], decision,
        status_time="2024-01-02T00:00:00Z",
    )
    _rewrite_evidence(tmp_path, supply, lambda artifact: artifact.__setitem__("source_proof", late_proof))
    result = evaluate_coverage(_contract(), [row], tmp_path)
    reasons = " ".join(result["exclusions"][0]["reasons"])
    assert "Coin Metrics status_time is after decision_at" in reasons


def test_structural_metadata_without_retained_bytes_can_never_open_labels(tmp_path):
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    result = evaluate_coverage(_contract(), [row])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["source_verification"] == "UNAVAILABLE"


def test_forged_allowed_source_value_or_digest_cannot_open_labels(tmp_path):
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    row["features"]["price"]["value"] = 999
    result = evaluate_coverage(_contract(), [row], tmp_path)
    assert "does not match retained artifact" in " ".join(result["exclusions"][0]["reasons"])

    row = _snapshot(tmp_path, "c", "2024-01-01T00:00:00Z")
    row["features"]["price"]["raw_digest_sha256"] = "0" * 64
    result = evaluate_coverage(_contract(), [row], tmp_path)
    assert "SHA-256 mismatch" in " ".join(result["exclusions"][0]["reasons"])


def test_single_day_liquidity_cannot_satisfy_30d_gate(tmp_path):
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z", liquidity_days=1)
    result = evaluate_coverage(_contract(), [row], tmp_path)
    assert "requires all 30 completed UTC daily quote-volume observations" in " ".join(result["exclusions"][0]["reasons"])


@pytest.mark.parametrize("key", ["outcome", "reached_2x", "future_return", "target_hit_at"])
def test_outcome_leakage_is_rejected_before_label_open(tmp_path, key):
    row = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    row["research"] = {key: "leak"}
    with pytest.raises(ValueError, match="outcome-derived key forbidden"):
        evaluate_coverage(_contract(), [row], tmp_path)


def test_sparse_asset_does_not_count_toward_minimum(tmp_path):
    rows = [
        _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
    ]
    result = evaluate_coverage(_contract(), rows, tmp_path)
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
    result = evaluate_coverage(_contract(), [row], tmp_path)
    assert expected in " ".join(result["exclusions"][0]["reasons"])


def test_duplicate_decision_rows_cannot_inflate_coverage(tmp_path):
    duplicate = _snapshot(tmp_path, "a", "2024-01-01T00:00:00Z")
    rows = [
        duplicate,
        json.loads(json.dumps(duplicate)),
        _snapshot(tmp_path, "a", "2024-01-08T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-01T00:00:00Z"),
        _snapshot(tmp_path, "b", "2024-01-08T00:00:00Z"),
    ]
    result = evaluate_coverage(_contract(), rows, tmp_path)
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["duplicate_snapshot_key_count"] == 1
    assert result["per_asset_snapshot_counts"] == {"a": 1, "b": 2}


def test_contract_rejects_raw_liquidity_or_unfrozen_grid():
    contract = _contract()
    contract["source_eligibility"]["liquidity_usd"] = [BINANCE]
    with pytest.raises(ValueError, match="raw caller values are forbidden"):
        validate_contract(contract)
    contract = _contract()
    contract["historical_universe_rule"]["decision_grid"] = "DAILY"
    with pytest.raises(ValueError, match="MONDAY_00_UTC_WEEKLY"):
        validate_contract(contract)


def test_actual_frozen_contract_is_fail_closed_without_coverage():
    root = Path(__file__).parents[1]
    contract = json.loads((root / "money_intelligence/2x_cohort_001_preflight_contract.json").read_text())
    validate_contract(contract)
    result = evaluate_coverage(contract, [])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["outcome_access"] == "SEALED"
    assert result["forward_formation_status"] == "BLOCKED_UNTIL_TRUSTED_RECEIPT"
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False

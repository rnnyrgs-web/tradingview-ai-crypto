import json
from pathlib import Path

import pytest

from big_move_prospective_snapshot import digest, evaluate_snapshot

TRAD_BLOB = "525b6a794e763569fbc9430f70fc725b10388b85"


def test_evidence_argument_must_bind_exact_frozen_feature_record():
    contract = json.loads(Path("money_intelligence/2x_prospective_snapshot_contract_v1.json").read_text())
    unknown = {"status": "UNKNOWN", "reason": "not source-authenticated"}
    base = {
        "status": "KNOWN",
        "source_id": "TEST_PROVIDER",
        "source_locator": "https://provider.example/evidence",
        "source_observed_at": "2026-09-21T15:00:00Z",
        "source_available_at": "2026-09-21T15:00:10Z",
        "captured_at": "2026-09-21T15:00:20Z",
        "raw_sha256": "a" * 64,
        "receipt_sha256": "b" * 64,
        "receipt_kind": "TRUSTED_REMOTE_ACQUISITION_ATTESTATION",
        "transform_id": "TEST_TRANSFORM",
        "transform_version": "1",
    }
    features = {family: dict(unknown) for family in contract["feature_families"]}
    for family, value in {
        "stable_identity": {"canonical_asset_id": "asset:test"},
        "venue_membership": {"active_spot": True},
        "liquidity_proxy": {"trailing_30d_quote_volume_usd": 20_000_000},
        "market_regime": {"regime": "BTC_RISK_ON"},
    }.items():
        features[family] = dict(base, value=value)
    features["strict_tradability"] = dict(base, value={
        "state": "STRICT_TRADABLE",
        "contract_artifact_id": "2X-TRADABILITY-001-v1",
        "contract_git_blob_sha": TRAD_BLOB,
        "execution_band_usd": 10000,
        "microstructure_evidence_sha256": "c" * 64,
        "window_start_at": "2026-09-21T09:00:00Z",
        "window_end_at": "2026-09-21T15:00:00Z",
        "metrics": {
            "independent_snapshots": 6,
            "missing_fraction": 0.0,
            "median_spread_bps": 12.0,
            "entry_vwap_slippage_bps": 25.0,
            "depth_coverage_ratio": 1.25,
        },
    })

    snapshot = {
        "schema": "two_x_prospective_snapshot.v1",
        "snapshot_id": "binding-test",
        "information_cutoff": "2026-09-21T15:55:00Z",
        "created_at": "2026-09-21T15:56:00Z",
        "assets": [{
            "asset_id": "asset:test",
            "venue_symbols": {"BINANCE_SPOT": "TESTUSDT"},
            "horizon_days": 90,
            "target_multiple": 2.0,
            "invalidation_rule": "frozen research invalidation",
            "features": features,
            "evidence_for": [{
                "statement": "Liquidity is known.",
                "classification": "FACT",
                "feature_family": "liquidity_proxy",
                "record_sha256": "d" * 64,
            }],
            "evidence_against": [{
                "statement": "Spot-flow evidence is unknown.",
                "classification": "UNKNOWN",
                "feature_family": "spot_participation_flow",
                "record_sha256": digest(features["spot_participation_flow"]),
            }],
        }],
    }

    with pytest.raises(ValueError, match="does not bind the frozen feature record"):
        evaluate_snapshot(contract, snapshot, verified_receipt_sha256s={"b" * 64})

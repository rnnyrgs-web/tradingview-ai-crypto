import json
from pathlib import Path

import pytest

from big_move_prospective_snapshot import (
    digest,
    evaluate_snapshot,
    strict_tradability_derivation_sha256,
)

CONTRACT_PATH = Path("money_intelligence/2x_prospective_snapshot_contract_v1.json")
TRAD_BLOB = "525b6a794e763569fbc9430f70fc725b10388b85"
RECEIPT_SHA = "b" * 64


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def _known(value, *, transform_id="TEST_TRANSFORM", transform_version="1"):
    return {
        "status": "KNOWN",
        "source_id": "TEST_PROVIDER",
        "source_locator": "https://provider.example/evidence",
        "source_observed_at": "2026-09-21T15:00:00Z",
        "source_available_at": "2026-09-21T15:00:10Z",
        "captured_at": "2026-09-21T15:00:20Z",
        "raw_sha256": "a" * 64,
        "receipt_sha256": RECEIPT_SHA,
        "receipt_kind": "TRUSTED_REMOTE_ACQUISITION_ATTESTATION",
        "transform_id": transform_id,
        "transform_version": transform_version,
        "value": value,
    }


def _strict_value(window_start_at):
    return {
        "state": "STRICT_TRADABLE",
        "contract_artifact_id": "2X-TRADABILITY-001-v1",
        "contract_git_blob_sha": TRAD_BLOB,
        "execution_band_usd": 10000,
        "microstructure_evidence_sha256": "0" * 64,
        "window_start_at": window_start_at,
        "window_end_at": "2026-09-21T15:00:00Z",
        "metrics": {
            "independent_snapshots": 6,
            "missing_fraction": 0.0,
            "median_spread_bps": 12.0,
            "entry_vwap_slippage_bps": 25.0,
            "depth_coverage_ratio": 1.25,
        },
    }


def _snapshot(window_start_at):
    contract = _contract()
    unknown = {"status": "UNKNOWN", "reason": "not source-authenticated at cutoff"}
    features = {family: dict(unknown) for family in contract["feature_families"]}
    features["stable_identity"] = _known({"canonical_asset_id": "asset:test"})
    features["venue_membership"] = _known({"active_spot": True})
    features["liquidity_proxy"] = _known(
        {"trailing_30d_quote_volume_usd": 25_000_000}
    )
    features["market_regime"] = _known({"regime": "BTC_RISK_ON"})
    features["strict_tradability"] = _known(
        _strict_value(window_start_at),
        transform_id="PIT_MICROSTRUCTURE_TRADABILITY_V1",
        transform_version="1",
    )
    strict = features["strict_tradability"]
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, contract)
    )

    return {
        "schema": "two_x_prospective_snapshot.v1",
        "snapshot_id": "strict-window-regression",
        "information_cutoff": "2026-09-21T15:55:00Z",
        "created_at": "2026-09-21T15:56:00Z",
        "assets": [
            {
                "asset_id": "asset:test",
                "venue_symbols": {"BINANCE_SPOT": "TESTUSDT"},
                "horizon_days": 90,
                "target_multiple": 2.0,
                "invalidation_rule": "frozen research invalidation",
                "features": features,
                "evidence_for": [
                    {
                        "statement": "Liquidity proxy is known.",
                        "classification": "FACT",
                        "feature_family": "liquidity_proxy",
                        "record_sha256": digest(features["liquidity_proxy"]),
                    }
                ],
                "evidence_against": [
                    {
                        "statement": "Spot-flow evidence is unavailable.",
                        "classification": "UNKNOWN",
                        "feature_family": "spot_participation_flow",
                        "record_sha256": digest(features["spot_participation_flow"]),
                    }
                ],
            }
        ],
    }


def _derivation_sha(snapshot):
    return snapshot["assets"][0]["features"]["strict_tradability"]["value"][
        "microstructure_evidence_sha256"
    ]


def test_exact_frozen_six_hour_window_remains_positive():
    snapshot = _snapshot("2026-09-21T09:00:00Z")
    result = evaluate_snapshot(
        _contract(),
        snapshot,
        verified_receipt_sha256s={RECEIPT_SHA},
        verified_strict_derivation_sha256s={_derivation_sha(snapshot)},
    )
    assert result["assets"][0]["status"] == "MECHANISM_REVIEW_READY"
    assert result["formation_authority"] is False
    assert result["prediction_authority"] is False
    assert result["ranking_authority"] is False


def test_short_favorable_window_fails_even_with_fresh_verified_derivation():
    snapshot = _snapshot("2026-09-21T14:55:00Z")
    derivation = _derivation_sha(snapshot)

    with pytest.raises(ValueError, match="window shorter than frozen lookback"):
        evaluate_snapshot(
            _contract(),
            snapshot,
            verified_receipt_sha256s={RECEIPT_SHA},
            verified_strict_derivation_sha256s={derivation},
        )


def test_window_longer_than_frozen_lookback_still_fails():
    snapshot = _snapshot("2026-09-21T08:00:00Z")
    derivation = _derivation_sha(snapshot)

    with pytest.raises(ValueError, match="window exceeds frozen lookback"):
        evaluate_snapshot(
            _contract(),
            snapshot,
            verified_receipt_sha256s={RECEIPT_SHA},
            verified_strict_derivation_sha256s={derivation},
        )

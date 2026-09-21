import copy
import json
from pathlib import Path

import pytest

from big_move_prospective_snapshot import (
    digest,
    evaluate_snapshot,
    strict_tradability_derivation_sha256,
    validate_contract,
)

CONTRACT_PATH = Path("money_intelligence/2x_prospective_snapshot_contract_v1.json")
TRAD_BLOB = "525b6a794e763569fbc9430f70fc725b10388b85"
VERIFIED = {"b" * 64}


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def _known(
    value,
    *,
    observed="2026-09-21T15:00:00Z",
    kind="TRUSTED_REMOTE_ACQUISITION_ATTESTATION",
    transform_id="TEST_TRANSFORM",
    transform_version="1",
):
    return {
        "status": "KNOWN",
        "source_id": "TEST_PROVIDER",
        "source_locator": "https://provider.example/evidence",
        "source_observed_at": observed,
        "source_available_at": "2026-09-21T15:00:10Z",
        "captured_at": "2026-09-21T15:00:20Z",
        "raw_sha256": "a" * 64,
        "receipt_sha256": "b" * 64,
        "receipt_kind": kind,
        "transform_id": transform_id,
        "transform_version": transform_version,
        "value": value,
    }


def _unknown(reason="not source-authenticated at cutoff"):
    return {"status": "UNKNOWN", "reason": reason}


def _strict(*, state="STRICT_TRADABLE", spread=12.0, band=10000, blob=TRAD_BLOB):
    return {
        "state": state,
        "contract_artifact_id": "2X-TRADABILITY-001-v1",
        "contract_git_blob_sha": blob,
        "execution_band_usd": band,
        "microstructure_evidence_sha256": "c" * 64,
        "window_start_at": "2026-09-21T09:00:00Z",
        "window_end_at": "2026-09-21T15:00:00Z",
        "metrics": {
            "independent_snapshots": 6,
            "missing_fraction": 0.0,
            "median_spread_bps": spread,
            "entry_vwap_slippage_bps": 25.0,
            "depth_coverage_ratio": 1.25,
        },
    }


def _snapshot(*, receipt_kind="TRUSTED_REMOTE_ACQUISITION_ATTESTATION"):
    contract = _contract()
    features = {family: _unknown() for family in contract["feature_families"]}
    features["stable_identity"] = _known({"canonical_asset_id": "asset:test"}, kind=receipt_kind)
    features["venue_membership"] = _known({"active_spot": True}, kind=receipt_kind)
    features["liquidity_proxy"] = _known({"trailing_30d_quote_volume_usd": 25_000_000}, kind=receipt_kind)
    features["strict_tradability"] = _known(
        _strict(),
        kind=receipt_kind,
        transform_id="PIT_MICROSTRUCTURE_TRADABILITY_V1",
        transform_version="1",
    )
    strict = features["strict_tradability"]
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, contract)
    )
    features["market_regime"] = _known({"regime": "BTC_RISK_ON"}, kind=receipt_kind)
    return {
        "schema": "two_x_prospective_snapshot.v1",
        "snapshot_id": "2X-PROSPECTIVE-20260921T1555Z-v1",
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
                "statement": "Liquidity proxy is known.",
                "classification": "FACT",
                "feature_family": "liquidity_proxy",
                "record_sha256": digest(features["liquidity_proxy"]),
            }],
            "evidence_against": [{
                "statement": "Spot-flow evidence is unavailable.",
                "classification": "UNKNOWN",
                "feature_family": "spot_participation_flow",
                "record_sha256": digest(features["spot_participation_flow"]),
            }],
        }],
    }


def _derivation_sha(snapshot):
    strict = snapshot["assets"][0]["features"]["strict_tradability"]
    return strict["value"]["microstructure_evidence_sha256"]


def _evaluate_ready(snapshot=None):
    snap = _snapshot() if snapshot is None else snapshot
    return evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
        verified_strict_derivation_sha256s={_derivation_sha(snap)},
    )


def test_contract_pins_freshness_tradability_and_feature_schema():
    contract = _contract()
    validate_contract(contract)
    assert contract["feature_value_schema"] == "two_x_feature_values.v1"
    assert contract["strict_tradability_binding"]["git_blob_sha"] == TRAD_BLOB
    assert contract["freshness_max_age_seconds"]["strict_tradability"] == 3600
    assert contract["formation_authority"] is False


def test_ready_requires_out_of_band_verified_receipts():
    result = _evaluate_ready()
    assert result["assets"][0]["status"] == "MECHANISM_REVIEW_READY"
    assert result["formation_authority"] is False
    assert result["prospective_chronology_authority"] is False
    assert result["snapshot_time_authority"] == "SELF_REPORTED_NOT_NON_BACKDATEABLE"
    assert result["verified_strict_derivation_count"] == 1


def test_default_unverified_receipts_fail_closed():
    result = evaluate_snapshot(_contract(), _snapshot())
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert "MANDATORY_RECEIPT_UNVERIFIED:stable_identity" in result["assets"][0]["blockers"]


def test_unverified_research_receipt_cannot_be_whitelisted():
    snap = _snapshot(receipt_kind="UNVERIFIED_RESEARCH_RECEIPT")
    result = evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
        verified_strict_derivation_sha256s={_derivation_sha(snap)},
    )
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert "STRICT_TRADABILITY_RECEIPT_KIND_UNTRUSTED" in result["assets"][0]["blockers"]


def test_strict_tradability_wrong_contract_blob_rejected():
    snap = _snapshot()
    snap["assets"][0]["features"]["strict_tradability"]["value"]["contract_git_blob_sha"] = "d" * 40
    with pytest.raises(ValueError, match="contract identity mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_strict_tradability_nonfrozen_band_rejected():
    snap = _snapshot()
    snap["assets"][0]["features"]["strict_tradability"]["value"]["execution_band_usd"] = 12345
    with pytest.raises(ValueError, match="execution band"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_strict_tradability_threshold_is_recomputed():
    snap = _snapshot()
    snap["assets"][0]["features"]["strict_tradability"]["value"]["metrics"]["median_spread_bps"] = 50.01
    with pytest.raises(ValueError, match="frozen #519 thresholds"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_stale_but_chronologically_valid_mandatory_evidence_rejected():
    snap = _snapshot()
    rec = snap["assets"][0]["features"]["venue_membership"]
    rec["source_observed_at"] = "2026-09-21T14:00:00Z"
    rec["source_available_at"] = "2026-09-21T14:00:10Z"
    rec["captured_at"] = "2026-09-21T14:00:20Z"
    with pytest.raises(ValueError, match="stale under frozen freshness policy"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_liquidity_proxy_cannot_substitute_for_unknown_strict_tradability():
    snap = _snapshot()
    strict = snap["assets"][0]["features"]["strict_tradability"]
    strict["value"] = {
        "state": "UNKNOWN_TRADABILITY",
        "contract_artifact_id": "2X-TRADABILITY-001-v1",
        "contract_git_blob_sha": TRAD_BLOB,
        "execution_band_usd": 10000,
        "microstructure_evidence_sha256": "c" * 64,
        "reason": "no PIT depth/spread receipt",
    }
    result = evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)
    assert "STRICT_TRADABILITY_NOT_CLEAR:UNKNOWN_TRADABILITY" in result["assets"][0]["blockers"]


def test_valid_acquisition_receipt_without_verified_derivation_fails_closed():
    snap = _snapshot()
    result = evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
    )
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert (
        "STRICT_TRADABILITY_DERIVATION_UNVERIFIED"
        in result["assets"][0]["blockers"]
    )


def test_fabricated_favorable_metrics_cannot_reuse_verified_derivation():
    snap = _snapshot()
    trusted_derivation = _derivation_sha(snap)
    strict = snap["assets"][0]["features"]["strict_tradability"]
    strict["value"]["metrics"]["median_spread_bps"] = 1.0
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, _contract())
    )

    result = evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
        verified_strict_derivation_sha256s={trusted_derivation},
    )
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert (
        "STRICT_TRADABILITY_DERIVATION_UNVERIFIED"
        in result["assets"][0]["blockers"]
    )


def test_strict_derivation_cannot_be_replayed_across_raw_digest():
    snap = _snapshot()
    trusted_derivation = _derivation_sha(snap)
    strict = snap["assets"][0]["features"]["strict_tradability"]
    strict["raw_sha256"] = "d" * 64
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, _contract())
    )

    result = evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
        verified_strict_derivation_sha256s={trusted_derivation},
    )
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert (
        "STRICT_TRADABILITY_DERIVATION_UNVERIFIED"
        in result["assets"][0]["blockers"]
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda rec: rec["value"].__setitem__("execution_band_usd", 50000),
        lambda rec: rec["value"].__setitem__(
            "window_start_at", "2026-09-21T10:00:00Z"
        ),
    ],
)
def test_strict_derivation_cannot_be_replayed_across_band_or_window(mutator):
    snap = _snapshot()
    trusted_derivation = _derivation_sha(snap)
    strict = snap["assets"][0]["features"]["strict_tradability"]
    mutator(strict)
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, _contract())
    )

    result = evaluate_snapshot(
        _contract(),
        snap,
        verified_receipt_sha256s=VERIFIED,
        verified_strict_derivation_sha256s={trusted_derivation},
    )
    assert result["assets"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert (
        "STRICT_TRADABILITY_DERIVATION_UNVERIFIED"
        in result["assets"][0]["blockers"]
    )


def test_strict_transform_version_is_frozen():
    snap = _snapshot()
    strict = snap["assets"][0]["features"]["strict_tradability"]
    strict["transform_version"] = "2"
    strict["value"]["microstructure_evidence_sha256"] = (
        strict_tradability_derivation_sha256(strict, _contract())
    )
    with pytest.raises(ValueError, match="transform identity mismatch"):
        evaluate_snapshot(
            _contract(),
            snap,
            verified_receipt_sha256s=VERIFIED,
            verified_strict_derivation_sha256s={
                strict["value"]["microstructure_evidence_sha256"]
            },
        )


def test_microstructure_evidence_hash_must_bind_exact_metrics():
    snap = _snapshot()
    strict = snap["assets"][0]["features"]["strict_tradability"]
    strict["value"]["metrics"]["median_spread_bps"] = 1.0
    with pytest.raises(ValueError, match="does not bind"):
        evaluate_snapshot(
            _contract(),
            snap,
            verified_receipt_sha256s=VERIFIED,
            verified_strict_derivation_sha256s={_derivation_sha(snap)},
        )


def test_future_outcome_key_and_near_2x_target_are_rejected():
    snap = _snapshot()
    snap["assets"][0]["target_multiple"] = 2.0000000001
    with pytest.raises(ValueError, match="target_multiple"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)
    snap = _snapshot()
    snap["assets"][0]["features"]["relationship_graph"]["future_return"] = 1.1
    with pytest.raises(ValueError, match="future/outcome-derived"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_unknown_record_cannot_fake_value_or_chronology():
    snap = _snapshot()
    snap["assets"][0]["features"]["relationship_graph"]["value"] = "same-sector"
    with pytest.raises(ValueError, match="schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_duplicate_asset_identity_rejected_and_digest_deterministic():
    snap = _snapshot()
    reordered = {key: snap[key] for key in reversed(list(snap))}
    assert digest(snap) == digest(reordered)
    snap["assets"].append(copy.deepcopy(snap["assets"][0]))
    with pytest.raises(ValueError, match="duplicate asset_id"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_unknown_keys_fail_closed_at_contract_snapshot_asset_record_and_argument_boundaries():
    contract = _contract()
    contract["post90_peak_multiple"] = 3.4
    with pytest.raises(ValueError, match="contract schema mismatch"):
        validate_contract(contract)

    snap = _snapshot()
    snap["y90"] = 1
    with pytest.raises(ValueError, match="snapshot schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["post90_peak_multiple"] = 3.4
    with pytest.raises(ValueError, match="asset schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["features"]["stable_identity"]["y90"] = 1
    with pytest.raises(ValueError, match="KNOWN record schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["features"]["relationship_graph"]["post90_peak_multiple"] = 3.4
    with pytest.raises(ValueError, match="UNKNOWN record schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["evidence_for"][0]["peak90"] = 3.4
    with pytest.raises(ValueError, match="evidence argument schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)


def test_feature_family_value_shapes_reject_free_form_nested_future_payloads():
    snap = _snapshot()
    snap["assets"][0]["features"]["stable_identity"]["value"]["post90_peak_multiple"] = 3.4
    with pytest.raises(ValueError, match="stable_identity.value schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["features"]["liquidity_proxy"]["value"] = {"peak90": 3.4}
    with pytest.raises(ValueError, match="liquidity_proxy.value schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

    snap = _snapshot()
    snap["assets"][0]["features"]["strict_tradability"]["value"]["metrics"]["post90_peak_multiple"] = 3.4
    with pytest.raises(ValueError, match="strict_tradability.metrics schema mismatch"):
        evaluate_snapshot(_contract(), snap, verified_receipt_sha256s=VERIFIED)

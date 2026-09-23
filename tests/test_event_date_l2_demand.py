from __future__ import annotations

import copy

import pytest

from money_intelligence.event_date_l2_demand import (
    CHRONOLOGY_CONTRACT,
    DemandManifestError,
    INPUT_SCHEMA,
    build_demand_manifest,
    blocked_manifest,
)


DATASET = "a" * 64
MAIN = "b986b0e10fd120fa009f5b58e7052b739e287238"


def _case(
    case_id: str,
    *,
    role: str = "EVENT",
    instrument: str = "ETHUSDT",
    canonical_asset_id: str | None = None,
    start: str = "2024-01-01T00:00:00Z",
    end: str = "2024-01-01T01:00:00Z",
    bands: list[int] | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "role": role,
        "canonical_asset_id": canonical_asset_id or instrument.removesuffix("USDT").lower(),
        "venue": "BINANCE_SPOT",
        "instrument": instrument,
        "window_start": start,
        "window_end": end,
        "required_notional_bands_usd": bands or [1_000, 10_000],
        "chronology_contract": CHRONOLOGY_CONTRACT,
        "strict_l2_required": True,
        "strict_l2_reason": "OHLCV/ADV cannot prove same-time full-notional executable bid depth",
        "tradability_state": "UNKNOWN_TRADABILITY",
    }


def _handoff(cases: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": INPUT_SCHEMA,
        "cohort_id": "2X-COHORT-001",
        "dataset_fingerprint": DATASET,
        "authority": "HISTORICAL_EVENT_CONTROL_ONLY",
        "cases": cases,
    }


def test_overlapping_same_instrument_windows_are_deduplicated() -> None:
    handoff = _handoff(
        [
            _case("event-1", end="2024-01-01T02:00:00Z", bands=[1_000]),
            _case(
                "control-1",
                role="MATCHED_CONTROL",
                start="2024-01-01T01:30:00Z",
                end="2024-01-01T03:00:00Z",
                bands=[10_000, 50_000],
            ),
        ]
    )
    result = build_demand_manifest(handoff)
    assert result["source_case_count"] == 2
    assert result["deduplicated_request_count"] == 1
    assert result["chronology_contract"] == CHRONOLOGY_CONTRACT
    request = result["requests"][0]
    assert request["window_start"] == "2024-01-01T00:00:00Z"
    assert request["window_end"] == "2024-01-01T03:00:00Z"
    assert request["required_notional_bands_usd"] == [1_000, 10_000, 50_000]
    assert request["source_case_ids"] == ["control-1", "event-1"]
    assert request["source_roles"] == ["EVENT", "MATCHED_CONTROL"]
    assert request["canonical_asset_id"] == "eth"
    assert request["purchase_authority"] == "NONE"
    assert result["status"] == "USER_APPROVAL_REQUIRED_FOR_ANY_NONZERO_PAID_ACQUISITION"


def test_nonoverlapping_windows_remain_separate() -> None:
    result = build_demand_manifest(
        _handoff(
            [
                _case("event-1", end="2024-01-01T01:00:00Z"),
                _case("event-2", start="2024-01-02T00:00:00Z", end="2024-01-02T01:00:00Z"),
            ]
        )
    )
    assert result["deduplicated_request_count"] == 2


def test_different_instruments_never_merge() -> None:
    result = build_demand_manifest(
        _handoff(
            [
                _case("eth", instrument="ETHUSDT"),
                _case("sol", instrument="SOLUSDT"),
            ]
        )
    )
    assert result["deduplicated_request_count"] == 2


def test_one_instrument_cannot_be_transplanted_across_canonical_assets() -> None:
    handoff = _handoff(
        [
            _case("eth-real", instrument="ETHUSDT", canonical_asset_id="eth"),
            _case("eth-transplant", instrument="ETHUSDT", canonical_asset_id="unrelated-asset"),
        ]
    )
    with pytest.raises(DemandManifestError, match="cannot be bound to multiple canonical_asset_id"):
        build_demand_manifest(handoff)


def test_unrecognized_chronology_contract_cannot_enter_provider_demand() -> None:
    case = _case("event-1")
    case["chronology_contract"] = "NEAREST_NEIGHBOR_DEPTH_V0"
    with pytest.raises(DemandManifestError, match="CROSSING_EXECUTION_INTERVAL_INTERSECTION_V1"):
        build_demand_manifest(_handoff([case]))


def test_manifest_is_deterministic_under_input_permutation() -> None:
    first = _case("a", start="2024-01-01T00:00:00Z", end="2024-01-01T03:00:00Z")
    second = _case("b", role="MATCHED_CONTROL", start="2024-01-01T02:00:00Z", end="2024-01-01T04:00:00Z")
    a = build_demand_manifest(_handoff([first, second]))
    b = build_demand_manifest(_handoff([second, first]))
    assert a == b
    assert a["manifest_fingerprint"] == b["manifest_fingerprint"]


def test_case_must_remain_unknown_tradability_before_l2_evidence() -> None:
    case = _case("event-1")
    case["tradability_state"] = "TRADABLE_2X_HIT_AT_BAND"
    with pytest.raises(DemandManifestError, match="UNKNOWN_TRADABILITY"):
        build_demand_manifest(_handoff([case]))


def test_l2_requirement_cannot_be_inferred_or_backfilled() -> None:
    case = _case("event-1")
    case["strict_l2_required"] = False
    with pytest.raises(DemandManifestError, match="explicitly requiring strict L2"):
        build_demand_manifest(_handoff([case]))


def test_wrong_venue_or_symbol_fails_closed() -> None:
    wrong_venue = _case("event-1")
    wrong_venue["venue"] = "OKX_SPOT"
    with pytest.raises(DemandManifestError, match="BINANCE_SPOT"):
        build_demand_manifest(_handoff([wrong_venue]))

    wrong_symbol = _case("event-2")
    wrong_symbol["instrument"] = "ETH-USD-SWAP"
    with pytest.raises(DemandManifestError, match="Binance USDT"):
        build_demand_manifest(_handoff([wrong_symbol]))


def test_undeclared_fields_are_rejected_to_prevent_outcome_smuggling() -> None:
    case = _case("event-1")
    case["post_90d_peak_multiple"] = 4.2
    with pytest.raises(DemandManifestError, match="undeclared keys"):
        build_demand_manifest(_handoff([case]))


def test_duplicate_case_identity_fails_closed() -> None:
    case = _case("same")
    with pytest.raises(DemandManifestError, match="case_id values must be unique"):
        build_demand_manifest(_handoff([case, copy.deepcopy(case)]))


def test_paid_authority_is_never_emitted() -> None:
    result = build_demand_manifest(_handoff([_case("event-1")]))
    assert result["purchase_authority"] == "NONE"
    assert result["cost_quote"] == "NOT_OBTAINED_NO_PURCHASE_OR_PLAN_SELECTION"
    assert result["label_authority"] == "NONE"
    assert result["candidate_authority"] == "NONE"
    assert result["model_authority"] == "NONE"
    assert result["broker_trading_authority"] == "NONE"


def test_empty_authorized_handoff_is_not_fabricated_into_demand() -> None:
    result = build_demand_manifest(_handoff([]))
    assert result["status"] == "NO_L2_DEMAND"
    assert result["source_case_count"] == 0
    assert result["deduplicated_request_count"] == 0
    assert result["requests"] == []


def test_missing_cohort_is_a_durable_blocker_not_synthetic_cases() -> None:
    result = blocked_manifest(
        reason="SURVIVOR_SAFE_EVENT_CONTROL_COHORT_NOT_YET_POPULATED",
        main_sha=MAIN,
    )
    assert result["status"] == "BLOCKED_INPUT_COHORT_NOT_POPULATED"
    assert result["requests"] == []
    assert result["purchase_authority"] == "NONE"
    assert result["label_authority"] == "NONE"
    assert len(result["manifest_fingerprint"]) == 64

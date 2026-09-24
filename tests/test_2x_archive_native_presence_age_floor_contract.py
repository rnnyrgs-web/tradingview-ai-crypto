import json
from datetime import datetime, timezone
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "money_intelligence"
    / "2x_archive_native_presence_age_floor_contract_v1.json"
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_canary_is_outcome_blind_and_chronologically_exact():
    contract = _contract()
    canary = contract["frozen_canary"]
    assert contract["schema"] == "two_x_archive_native_presence_history_span_contract.v1"
    assert contract["artifact_id"] == "2X-ARCHIVE-NATIVE-PRESENCE-HISTORY-SPAN-001-v1"
    assert contract["status"] == "PREDECLARED_BLOCKED_TRUSTED_ATTESTED_ROWS_NOT_YET_CONSUMABLE"
    assert contract["outcome_access"] == "SEALED"
    assert contract["broker_live_trading"] == "OFF"
    assert canary["venue"] == "BINANCE_SPOT"
    assert canary["symbol"] == "BTCUSDT"
    assert canary["quote_asset"] == "USDT"
    assert canary["cadence"] == "1d"
    assert canary["decision_at"] == "2021-02-01T00:00:00Z"

    presence = canary["presence_archive"]
    assert presence["required_row_date"] == "2021-01-31"
    assert presence["required_open_time_ms"] == 1612051200000
    assert presence["required_close_time_ms"] == 1612137599999
    assert presence["required_relation_to_decision"] == "IMMEDIATELY_PRECEDING_COMPLETED_UTC_DAY"
    assert presence["required_close_time_ms"] + 1 == int(_utc(canary["decision_at"]).timestamp() * 1000)

    anchor = canary["history_span_anchor_archive"]
    assert anchor["required_row_date"] == "2020-07-31"
    assert anchor["required_open_time_ms"] == 1596153600000
    assert anchor["required_close_time_ms"] == 1596239999999
    anchor_end_exclusive = datetime.fromtimestamp((anchor["required_close_time_ms"] + 1) / 1000, tz=timezone.utc)
    elapsed_full_days = (_utc(canary["decision_at"]) - anchor_end_exclusive).days
    assert elapsed_full_days == 184
    assert anchor["minimum_elapsed_full_days_from_completed_row_end"] == elapsed_full_days
    assert elapsed_full_days >= 180


def test_trusted_inputs_require_external_identity_not_caller_clocks():
    contract = _contract()
    trusted = contract["trusted_input_contract"]
    assert trusted["archive_and_checksum_each_require_independent_trusted_attestation"] is True
    assert set(trusted["required_identity_bindings"]) == {
        "repository",
        "trusted_acquisition_workflow",
        "canonical_main_ref_and_source_sha",
        "workflow_run_and_artifact",
        "attested_subject_digest",
        "trusted_acquisition_receipt_bytes_and_digest",
        "provider_url",
        "provider_response_sha256",
        "provider_response_byte_count",
    }
    assert trusted["checksum_semantics"] == "EXACT_ARCHIVE_FILENAME_AND_SHA256"
    assert trusted["zip_semantics"] == "SAFE_SINGLE_EXPECTED_MEMBER_ONLY"
    assert trusted["provider_row_time_authority"] == "SOURCE_NATIVE_OPEN_AND_CLOSE_TIME_ONLY"
    assert trusted["caller_event_time_authority"] == "NONE"
    assert trusted["local_file_time_authority"] == "NONE"
    assert trusted["issue_or_comment_time_authority"] == "NONE"


def test_presence_and_history_span_are_positive_evidence_only():
    contract = _contract()
    presence = contract["presence_rule"]
    assert presence["require_trade_count_gt_zero"] is True
    assert presence["require_base_asset_volume_gt_zero"] is True
    assert presence["require_quote_asset_volume_gt_zero"] is True
    assert presence["positive_authority"] == "PROVIDER_NATIVE_PIT_MARKET_PRESENCE_ONLY"
    assert presence["missing_or_untrusted_evidence_state"] == "UNKNOWN"
    assert presence["missing_evidence_is_false_membership"] is False
    assert presence["archive_object_existence_alone_has_presence_authority"] is False

    history = contract["observed_history_span_rule"]
    assert history["threshold_days"] == 180
    assert history["claim"] == "TRADING_OBSERVED_AT_LEAST_180D_BEFORE_DECISION"
    assert history["continuous_listing_authority"] == "NONE"
    assert history["listing_age_ge_180d_authority"] == "NONE"
    assert history["exact_first_trade_or_listing_time_authority"] == "NONE"
    assert history["missing_or_untrusted_evidence_state"] == "UNKNOWN"
    assert history["archive_absence_has_delisting_authority"] is False
    assert history["archive_absence_has_negative_control_authority"] is False


def test_sparse_positive_rows_cannot_be_reinterpreted_as_listing_age():
    contract = _contract()
    history = contract["observed_history_span_rule"]
    boundary = contract["versioned_consumer_boundary"]

    assert "listing" not in history["claim"].lower()
    assert history["continuous_listing_authority"] == "NONE"
    assert history["listing_age_ge_180d_authority"] == "NONE"
    assert boundary["cohort_listing_age_gate_authority"] == "NONE_REQUIRES_TRUSTED_LISTING_START_OR_CONTINUITY_EVIDENCE"
    assert "SPARSE_ROWS_REINTERPRETED_AS_CONTINUOUS_LISTING_AGE" in contract["falsifiers"]
    assert contract["forbidden_authority"]["listing_age_ge_180d"] is False
    assert contract["forbidden_authority"]["continuous_listing"] is False


def test_legacy_exact_listing_age_semantics_are_not_reinterpreted():
    contract = _contract()
    boundary = contract["versioned_consumer_boundary"]
    assert boundary["legacy_exact_age_transform"] == "DERIVED_BINANCE_LISTING_AGE_DAYS_V1"
    assert boundary["legacy_basis"] == "first_verified_venue_trade"
    assert boundary["legacy_transform_must_not_be_reinterpreted"] is True
    assert boundary["new_observed_history_transform"] == "DERIVED_BINANCE_OBSERVED_TRADING_HISTORY_GE_180D_V1"
    assert boundary["cohort_listing_age_gate_authority"] == "NONE_REQUIRES_TRUSTED_LISTING_START_OR_CONTINUITY_EVIDENCE"
    assert boundary["membership_provenance_target"] == "binance_market_presence_provenance.v1"
    assert boundary["current_preflight_authority"] == "NONE_UNTIL_SEPARATELY_REVIEWED_VERSIONED_CONSUMER"


def test_contract_grants_no_listing_age_label_model_candidate_spend_or_trade_authority():
    contract = _contract()
    forbidden = contract["forbidden_authority"]
    expected_false = {
        "exact_listing_time",
        "listing_age_ge_180d",
        "continuous_listing",
        "delisting_time",
        "matched_nonwinner",
        "historical_2x_label",
        "usd_liquidity",
        "strict_tradability",
        "precursor_or_archetype_effect",
        "relationship_graph_effect",
        "competing_risk_model",
        "prospective_candidate",
        "promotion",
        "spend",
        "broker_connection",
        "live_trading",
    }
    assert set(forbidden) == expected_false
    assert all(forbidden[key] is False for key in expected_false)
    assert contract["strict_tradability_dependency"] == "PIT_EVENT_TIME_DEPTH_SPREAD_SLIPPAGE_REQUIRED_UNDER_519"


def test_falsifier_matrix_keeps_survivorship_timestamp_and_listing_age_laundering_closed():
    contract = _contract()
    falsifiers = set(contract["falsifiers"])
    assert {
        "UNATTESTED_LOCAL_ARCHIVE_AND_CHECKSUM",
        "WRONG_SYMBOL_MARKET_QUOTE_ASSET_CADENCE_OR_MONTH",
        "PRESENCE_ROW_NOT_IMMEDIATELY_PREDECISION",
        "PRESENCE_ROW_POSTDECISION",
        "HISTORY_ANCHOR_ROW_AFTER_180D_CUTOFF",
        "SPARSE_ROWS_REINTERPRETED_AS_CONTINUOUS_LISTING_AGE",
        "TARDIS_ENUMERATION_OR_QUEUE_LINEAGE_AS_MEMBERSHIP_PROOF",
        "CALLER_TIMESTAMP_OVERRIDES_NATIVE_ROW_TIME",
        "ARCHIVE_OBJECT_EXISTENCE_WITHOUT_AUTHENTICATED_ROW_CONTENT",
    } <= falsifiers

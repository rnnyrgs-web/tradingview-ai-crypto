from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from research_artifact import sha256_hex

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "orchestration" / "data" / "c101h_funding_data_contract_v1.json"


def _load():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_digest_and_frozen_consumer_are_deterministic():
    contract = _load()
    unsigned = copy.deepcopy(contract)
    expected = unsigned.pop("contract_sha256")
    assert sha256_hex(unsigned) == expected
    assert contract["contract_id"] == "C101-H-BINANCE-PIT-DATA-v1"
    assert contract["consumer"] == {
        "candidate_id": "C101-H",
        "cohort": "COHORT-001",
        "mechanism": "delta-neutral positive-funding carry",
        "use": "DATA_PREFLIGHT_ONLY_UNTIL_QUALIFIED",
    }


def test_source_universe_and_coverage_are_frozen_before_outcomes():
    contract = _load()
    source = contract["frozen_source"]
    assert source["venue"] == "BINANCE"
    assert source["spot_market"] == "SPOT"
    assert source["perpetual_market"] == "USD-M_PERPETUAL"
    assert source["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert source["symbol_substitution_allowed"] is False
    assert source["venue_substitution_allowed"] is False
    assert source["coverage_shortening_after_outcomes_allowed"] is False
    assert datetime.fromisoformat(source["development_coverage_end_utc"]) < datetime.fromisoformat(source["protected_start_utc"])


def test_funding_cashflows_use_source_native_events_and_actual_intervals():
    contract = _load()
    semantics = contract["timestamp_and_funding_semantics"]
    assert semantics["funding_is_event_based"] is True
    assert semantics["funding_event_timestamp_is_source_native"] is True
    assert semantics["funding_interval_seconds_is_derived_from_adjacent_source_events"] is True
    assert semantics["fixed_8h_interval_assumption_allowed"] is False
    assert semantics["funding_forward_fill_as_cashflow_allowed"] is False
    assert semantics["future_dated_funding_allowed"] is False


def test_raw_provenance_and_archive_corrections_fail_closed():
    contract = _load()
    provenance = contract["source_provenance"]
    assert provenance["public_data_repository_pinned_commit"] == "5c7f3197591c0d54d85dc43066226bc4c671d47a"
    assert provenance["raw_archive_and_checksum_retention_required"] is True
    assert provenance["archive_corrections_create_new_dataset_version"] is True
    assert provenance["silent_archive_mutation_allowed"] is False
    assert provenance["funding_path_requires_binance_hosted_object_verification"] is True
    assert "checksum mismatch or archive correction not versioned" in contract["fail_closed_conditions"]
    assert "source schema cannot be independently verified" in contract["fail_closed_conditions"]


def test_data_ready_reuses_single_shared_cryptographic_acquisition_boundary():
    contract = _load()
    provenance = contract["source_provenance"]
    assert provenance["trusted_acquisition_required"] is True
    assert provenance["local_archive_checksum_pair_sufficient_for_data_ready"] is False
    assert provenance["trusted_acquisition_contract_id"] == "PIT-TRUSTED-REMOTE-ACQUISITION-001-v1"
    assert provenance["trusted_acquisition_expected_workflow"] == ".github/workflows/pit-trusted-remote-acquisition.yml"
    assert provenance["trusted_acquisition_source_ref"] == "refs/heads/main"
    assert provenance["trusted_attestation_predicate_type"] == "https://slsa.dev/provenance/v1"
    assert provenance["trusted_acquisition_required_request_shapes"] == [
        "BINANCE_C101H_ARCHIVE",
        "BINANCE_C101H_CHECKSUM",
    ]
    assert provenance["trusted_acquisition_dependency_state"] == "READY_FOR_TRUSTED_DIRECT_OBJECT_ACQUISITION"
    assert provenance["trusted_pair_consumer"] == (
        "c101h_binance_pair.verify_attested_c101h_archive_checksum_pair"
    )
    assert "trusted acquisition attestation missing, unverifiable, or signer/ref policy mismatch" in contract["fail_closed_conditions"]
    assert (
        "attested archive/checksum pair is not verified through the canonical C101-H pair consumer"
        in contract["fail_closed_conditions"]
    )
    assert "independently freeze the exact authenticated Binance funding CSV field order/types" in contract["exact_next_action"]


def test_contract_does_not_authorize_outcome_inspection_or_trading():
    contract = _load()
    safety = contract["scientific_safety"]
    assert safety["strategy_outcomes_may_be_computed_during_data_build"] is False
    assert safety["candidate_return_may_be_inspected_during_data_build"] is False
    assert safety["protected_oos_opened"] is False
    assert safety["genuine_forward_opened"] is False
    assert safety["trade_authority"] is False
    assert safety["promotion_authority"] is False
    assert safety["broker_connected"] is False


def test_acceptance_receipt_requires_reproducibility_gap_and_trusted_source_diagnostics():
    contract = _load()
    required = set(contract["qualification_receipt"]["required"])
    assert {
        "raw_archive_sha256",
        "checksum_sidecar_sha256",
        "normalized_dataset_sha256",
        "rows_per_symbol_and_source",
        "duplicate_count",
        "gap_count",
        "stale_count",
        "funding_interval_distribution_seconds",
        "parse_rerun_hash_equal",
        "trusted_acquisition_attestation_id",
        "trusted_acquisition_manifest_sha256",
        "trusted_requested_url",
        "trusted_final_url",
        "trusted_workflow_run_id",
        "trusted_workflow_sha",
    } <= required
    assert contract["qualification_receipt"]["accept_status"] == "DATA_READY_FOR_FROZEN_CONSUMER"
    assert contract["qualification_receipt"]["blocked_status"] == "DATA_BLOCKED"

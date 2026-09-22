from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT_PATH = ROOT / "money_intelligence" / "2x_trusted_final_resolution_contract_v1.json"
CHRONOLOGY_PATH = (
    ROOT
    / "money_intelligence"
    / "2x_trusted_final_resolution_policy_chronology_v1.json"
)
TRADABILITY_BINDING_PATH = (
    ROOT
    / "money_intelligence"
    / "2x_trusted_final_resolution_tradability_binding_v1.json"
)
TRADABILITY_PRECOMMITMENT_PATH = (
    ROOT / "money_intelligence" / "2x_tradability_precommitment_v1.json"
)
GATE_PATH = (
    ROOT
    / "money_intelligence"
    / "2x_trusted_final_resolution_preimplementation_gate_v1.json"
)
DOMAIN = b"2X_FINAL_RESOLUTION_CONTRACT_BUNDLE_V1"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _member_sha256(path: Path, payload: bytes | None = None) -> str:
    data = path.read_bytes() if payload is None else payload
    return hashlib.sha256(data).hexdigest()


def _governed_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (PARENT_PATH, CHRONOLOGY_PATH, TRADABILITY_BINDING_PATH),
            key=lambda p: p.relative_to(ROOT).as_posix(),
        )
    )


def _bundle_fingerprint(overrides: dict[str, bytes] | None = None) -> str:
    overrides = overrides or {}
    body = bytearray(DOMAIN)
    body.extend(b"\0")
    for path in _governed_paths():
        relative = path.relative_to(ROOT).as_posix()
        digest = _member_sha256(path, overrides.get(relative))
        body.extend(relative.encode("utf-8"))
        body.extend(b"\0")
        body.extend(digest.encode("ascii"))
        body.extend(b"\n")
    return hashlib.sha256(bytes(body)).hexdigest()


def test_preimplementation_contract_bundle_is_fail_closed() -> None:
    parent = _load(PARENT_PATH)
    chronology = _load(CHRONOLOGY_PATH)
    tradability = _load(TRADABILITY_BINDING_PATH)
    gate = _load(GATE_PATH)

    assert parent["contract_id"] == "2X-TRUSTED-FINAL-RESOLUTION-001-v1"
    assert chronology["contract_id"] == (
        "2X-TRUSTED-FINAL-RESOLUTION-POLICY-CHRONOLOGY-001-v1"
    )
    assert tradability["contract_id"] == (
        "2X-TRUSTED-FINAL-RESOLUTION-TRADABILITY-001-v1"
    )
    assert gate["contract_id"] == (
        "2X-TRUSTED-FINAL-RESOLUTION-PREIMPLEMENTATION-GATE-001-v1"
    )

    for contract in (parent, chronology, tradability, gate):
        assert contract["status"] == "PREDECLARED_NOT_IMPLEMENTED"
        authority = contract["authority"]
        for key in (
            "final_resolution_authority",
            "factory_metrics_authority",
            "candidate_ranking_authority",
            "model_fitting_authority",
            "broker_or_trading_authority",
        ):
            assert authority[key] is False

    assert chronology["parent_contract_id"] == parent["contract_id"]
    assert chronology["normative_relationship"]["required_with_parent_contract"] is True
    assert chronology["normative_relationship"]["no_authority_if_missing"] is True
    assert tradability["parent_contract_id"] == parent["contract_id"]
    assert tradability["normative_relationship"]["required_with_parent_contract"] is True
    assert tradability["normative_relationship"]["no_authority_if_missing"] is True

    assert gate["review_scope"] == {
        **gate["review_scope"],
        "artifact_type": "PREIMPLEMENTATION_SCIENTIFIC_CONTRACT_AND_CI_GUARD",
        "implementation_claimed": False,
        "deployment_claimed": False,
        "runtime_enforcement_claimed": False,
    }
    assert gate["implementation_gate"]["authority_until_complete"] == "NONE"
    assert gate["trusted_contract_registry"]["required"] is True


def test_governed_contract_set_and_identity_algorithm_are_exact() -> None:
    gate = _load(GATE_PATH)
    members = gate["governed_contracts"]

    assert members == [
        {
            "path": "money_intelligence/2x_trusted_final_resolution_contract_v1.json",
            "contract_id": "2X-TRUSTED-FINAL-RESOLUTION-001-v1",
            "required_status": "PREDECLARED_NOT_IMPLEMENTED",
        },
        {
            "path": "money_intelligence/2x_trusted_final_resolution_policy_chronology_v1.json",
            "contract_id": "2X-TRUSTED-FINAL-RESOLUTION-POLICY-CHRONOLOGY-001-v1",
            "required_status": "PREDECLARED_NOT_IMPLEMENTED",
        },
        {
            "path": "money_intelligence/2x_trusted_final_resolution_tradability_binding_v1.json",
            "contract_id": "2X-TRUSTED-FINAL-RESOLUTION-TRADABILITY-001-v1",
            "required_status": "PREDECLARED_NOT_IMPLEMENTED",
        },
    ]

    identity = gate["contract_bundle_identity"]
    assert identity["member_digest_algorithm"] == "SHA256_EXACT_UTF8_FILE_BYTES"
    assert identity["member_order"] == "LEXICOGRAPHIC_PATH_ASCENDING"
    assert identity["bundle_domain"] == DOMAIN.decode("ascii")
    assert identity["bundle_fingerprint_algorithm"] == (
        "SHA256(domain + NUL + repeated(path + NUL + member_sha256_hex + LF))"
    )

    first = _bundle_fingerprint()
    second = _bundle_fingerprint()
    assert first == second
    assert len(first) == 64


def test_one_byte_contract_mutation_changes_bundle_identity() -> None:
    baseline = _bundle_fingerprint()

    for path in _governed_paths():
        relative = path.relative_to(ROOT).as_posix()
        original = path.read_bytes()
        assert original
        mutated = original[:-1] + bytes([original[-1] ^ 1])
        assert _bundle_fingerprint({relative: mutated}) != baseline


def test_formation_identity_and_execution_policy_are_bound_before_future_authority() -> None:
    gate = _load(GATE_PATH)
    binding = gate["formation_binding"]

    assert binding["required_origin"] == "TRUSTED_NON_BACKDATEABLE_SERVER_FORMATION_RECEIPT"
    assert binding["caller_authored_formation_time_authority"] is False
    assert set(binding["must_bind"]) >= {
        "formation_sequence",
        "formation_receipt_fingerprint",
        "trusted_server_formation_time",
        "canonical_stable_asset_identity",
        "exact_venue_and_instrument_identity",
        "point_in_time_universe_membership_identity",
        "frozen_reference_price_and_time",
        "frozen_horizon_and_target",
        "forecast_or_formation_contract_fingerprint",
        "contract_bundle_fingerprint",
        "policy_receipt_fingerprint",
        "execution_policy_fingerprint",
        "evaluated_notional_bands_usd",
        "primary_success_band_usd_or_explicit_none",
        "frozen_execution_venue_policy",
    }

    registry = gate["trusted_contract_registry"]
    assert "at or before trusted server formation time" in registry[
        "confirmatory_chronology_rule"
    ]
    assert "refuse authoritative final resolution" in registry[
        "runtime_fail_closed_rule"
    ]
    assert "tradability precommitment artifact id/schema/exact deployed file SHA-256" in registry[
        "receipt_must_bind"
    ]


def test_tradability_companion_keeps_price_crossing_out_of_primary_success() -> None:
    tradability = _load(TRADABILITY_BINDING_PATH)
    precommitment = _load(TRADABILITY_PRECOMMITMENT_PATH)

    assert precommitment["artifact_id"] == "2X-TRADABILITY-001-v1"
    assert precommitment["execution_bands_usd"] == [1000, 10000, 50000, 100000]
    assert precommitment["strict_band_rules"]["maximum_median_spread_bps"] == 50
    assert precommitment["strict_band_rules"]["maximum_entry_vwap_slippage_bps"] == 100
    assert precommitment["principles"]["adv_only_cannot_establish_strict_tradability"] is True
    assert precommitment["principles"]["missing_microstructure_policy"] == "UNKNOWN_TRADABILITY"

    normative = tradability["normative_relationship"]
    assert normative["primary_factory_success"] == "TRADABLE_2X_HIT_AT_BAND"
    assert "descriptive PRICE_2X_CROSSING" in normative["parent_hit_semantics"]

    states = tradability["outcome_states"]
    assert states["PRICE_2X_CROSSING"]["factory_success_authority"] is False
    assert states["PRICE_HIT_TRADABILITY_UNKNOWN"]["factory_success_authority"] is False
    assert states["ILLIQUID_2X_RESEARCH_ONLY"]["factory_success_authority"] is False
    assert states["TRADABLE_2X_HIT_AT_BAND"]["primary_metrics_role"]

    crossing = tradability["crossing_side_execution"]
    assert crossing["limits"]["adv_or_volume_only_is_sufficient"] is False
    assert crossing["limits"]["maximum_median_or_contemporaneous_spread_bps"] == 50
    assert crossing["limits"]["maximum_exit_vwap_slippage_bps"] == 100
    assert "one-lot/isolated target trade" in crossing["flash_wick_rule"]
    assert "PRICE_HIT_TRADABILITY_UNKNOWN" in crossing["unknown_rule"]


def test_tradability_policy_is_ex_ante_and_fingerprint_bound() -> None:
    tradability = _load(TRADABILITY_BINDING_PATH)
    policy = tradability["ex_ante_execution_policy"]

    assert "at or before trusted server formation time" in policy["chronology"]
    assert "best-looking band after outcome" in policy["band_rule"]
    assert "substituted after the move" in policy["venue_rule"]
    assert set(policy["must_bind"]) >= {
        "tradability_precommitment_artifact_id_and_exact_file_sha256",
        "evaluated_notional_bands_usd",
        "primary_success_band_usd_or_explicit_none",
        "exact_execution_venue_and_instrument_identity_or_frozen_venue_set",
        "execution_policy_fingerprint",
    }

    required_fingerprint_members = set(tradability["final_resolution_fingerprint_must_bind"])
    assert {
        "execution_policy_fingerprint",
        "crossing_side_microstructure_evidence_identities",
        "tradable_hit_exact_time_or_censoring_bounds_per_band",
        "tradability_state_per_band",
        "tradability_evidence_revision_and_supersession_lineage",
    } <= required_fingerprint_members

    attacks = "\n".join(tradability["mandatory_red_green_tests"])
    assert "flash-wick" in attacks
    assert "excluded thin off-venue" in attacks
    assert "selected after outcome" in attacks
    assert "late authoritative microstructure revision" in attacks


def test_existing_contracts_retain_competing_risk_and_no_fake_expiry_guards() -> None:
    parent = _load(PARENT_PATH)
    chronology = _load(CHRONOLOGY_PATH)
    tradability = _load(TRADABILITY_BINDING_PATH)

    assert parent["final_states"]["EXPIRED"]["fail_closed_state_if_missing"] == (
        "CENSORED_GAP_NOT_EXPIRED"
    )
    assert parent["final_states"]["CENSORED_COMPETING_EVENT_ORDER"]["authority_rule"]
    assert parent["competing_risk_model_handoff"]["not_primary"] == "raw accuracy"
    assert chronology["eligibility_states"][
        "RESEARCH_ONLY_NONCONFIRMATORY_POLICY_CHRONOLOGY"
    ]
    assert "CENSORED_COMPETING_EVENT_ORDER" in tradability[
        "competing_event_integration"
    ]["rule"]
    assert chronology["broker_live_trading"] == "OFF"
    assert tradability["broker_live_trading"] == "OFF"

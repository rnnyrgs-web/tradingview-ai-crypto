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


def _bundle_fingerprint(overrides: dict[str, bytes] | None = None) -> str:
    overrides = overrides or {}
    members = sorted((PARENT_PATH, CHRONOLOGY_PATH), key=lambda p: p.relative_to(ROOT).as_posix())
    body = bytearray(DOMAIN)
    body.extend(b"\0")
    for path in members:
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
    gate = _load(GATE_PATH)

    assert parent["contract_id"] == "2X-TRUSTED-FINAL-RESOLUTION-001-v1"
    assert chronology["contract_id"] == (
        "2X-TRUSTED-FINAL-RESOLUTION-POLICY-CHRONOLOGY-001-v1"
    )
    assert gate["contract_id"] == (
        "2X-TRUSTED-FINAL-RESOLUTION-PREIMPLEMENTATION-GATE-001-v1"
    )

    assert parent["status"] == "PREDECLARED_NOT_IMPLEMENTED"
    assert chronology["status"] == "PREDECLARED_NOT_IMPLEMENTED"
    assert gate["status"] == "PREDECLARED_NOT_IMPLEMENTED"

    assert chronology["parent_contract_id"] == parent["contract_id"]
    assert chronology["normative_relationship"]["required_with_parent_contract"] is True
    assert chronology["normative_relationship"]["no_authority_if_missing"] is True

    for contract in (parent, chronology, gate):
        authority = contract["authority"]
        for key in (
            "final_resolution_authority",
            "factory_metrics_authority",
            "candidate_ranking_authority",
            "model_fitting_authority",
            "broker_or_trading_authority",
        ):
            assert authority[key] is False

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

    for path in (PARENT_PATH, CHRONOLOGY_PATH):
        relative = path.relative_to(ROOT).as_posix()
        original = path.read_bytes()
        assert original
        mutated = original[:-1] + bytes([original[-1] ^ 1])
        assert _bundle_fingerprint({relative: mutated}) != baseline


def test_formation_identity_is_bound_before_future_authority() -> None:
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
    }

    registry = gate["trusted_contract_registry"]
    assert "at or before trusted server formation time" in registry[
        "confirmatory_chronology_rule"
    ]
    assert "refuse authoritative final resolution" in registry[
        "runtime_fail_closed_rule"
    ]


def test_existing_contracts_retain_competing_risk_and_no_fake_expiry_guards() -> None:
    parent = _load(PARENT_PATH)
    chronology = _load(CHRONOLOGY_PATH)

    assert parent["final_states"]["EXPIRED"]["fail_closed_state_if_missing"] == (
        "CENSORED_GAP_NOT_EXPIRED"
    )
    assert parent["final_states"]["CENSORED_COMPETING_EVENT_ORDER"]["authority_rule"]
    assert parent["competing_risk_model_handoff"]["not_primary"] == "raw accuracy"
    assert chronology["eligibility_states"][
        "RESEARCH_ONLY_NONCONFIRMATORY_POLICY_CHRONOLOGY"
    ]
    assert chronology["broker_live_trading"] == "OFF"

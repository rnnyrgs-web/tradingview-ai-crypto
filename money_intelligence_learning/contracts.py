"""Frozen point-in-time contracts for causal Money Intelligence evidence."""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse

from profitability_learning.contracts import canonical, fingerprint, integer, number, text, timestamp


SAFE = {
    "research_only": True,
    "automatic_execution_authority": False,
    "strategy_mutation_authority": False,
    "trade_authority": False,
    "promotion_authority": False,
    "broker_connected": False,
}

MECHANISM_INPUT_FIELDS = {
    "schema_version", "mechanism_key", "claim", "causal_chain", "expected_direction",
    "expected_horizon_days", "falsifier", "transmission_variables", "matched_control_design",
    "regime_scope", "frozen_at", "information_cutoff", "prior_confidence",
    "decay_half_life_days", "minimum_supporting_sources", "minimum_matched_controls",
    "search_breadth", "target_assets", "downstream_lanes",
}
MECHANISM_FIELDS = MECHANISM_INPUT_FIELDS | {"mechanism_id", "contract_id"} | set(SAFE)
EVIDENCE_KINDS = {
    "SUPPORT", "CONTRADICTION", "MATCHED_CONTROL_SUPPORT", "MATCHED_CONTROL_FAILURE", "REVALIDATION",
}
EVIDENCE_INPUT_FIELDS = {
    "schema_version", "evidence_kind", "observed_at", "published_at", "available_at",
    "information_cutoff", "source", "independence_key", "strength", "structured_fact",
    "matched_control", "narrative_summary",
}
EVIDENCE_FIELDS = EVIDENCE_INPUT_FIELDS | {"evidence_id", "mechanism_id"} | set(SAFE)


def _text_list(value, name, *, minimum=1, maximum=32):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum or len(value) != len(set(value)):
        raise ValueError(f"{name} must contain distinct bounded text values")
    for item in value:
        text(item, name)
    return value


def _validate_url(value):
    parsed = urlparse(text(value, "source uri"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("source uri must be HTTPS")


def _freeze_mechanism(spec):
    if not isinstance(spec, dict) or set(spec) != MECHANISM_INPUT_FIELDS:
        raise ValueError("mechanism contract fields mismatch")
    contract = deepcopy(spec)
    if contract.get("schema_version") != 1:
        raise ValueError("unknown mechanism schema")
    key = text(contract.get("mechanism_key"), "mechanism key")
    text(contract.get("claim"), "claim")
    _text_list(contract.get("causal_chain"), "causal chain", minimum=2)
    if contract.get("expected_direction") not in {"POSITIVE", "NEGATIVE", "MIXED"}:
        raise ValueError("invalid expected direction")
    integer(contract.get("expected_horizon_days"), "expected horizon days", 1, 365)
    text(contract.get("falsifier"), "falsifier")
    _text_list(contract.get("transmission_variables"), "transmission variables")
    controls = contract.get("matched_control_design")
    if not isinstance(controls, dict) or set(controls) != {"control_group", "matching_variables", "failure_condition"}:
        raise ValueError("matched control design required")
    text(controls.get("control_group"), "control group")
    _text_list(controls.get("matching_variables"), "matching variables")
    text(controls.get("failure_condition"), "control failure condition")
    _text_list(contract.get("regime_scope"), "regime scope")
    cutoff, frozen = timestamp(contract.get("information_cutoff")), timestamp(contract.get("frozen_at"))
    if cutoff > frozen:
        raise ValueError("mechanism information cutoff after freeze")
    number(contract.get("prior_confidence"), "prior confidence", minimum=0)
    if contract["prior_confidence"] > 1:
        raise ValueError("prior confidence above one")
    integer(contract.get("decay_half_life_days"), "decay half life", 1, 3650)
    integer(contract.get("minimum_supporting_sources"), "minimum supporting sources", 1, 32)
    integer(contract.get("minimum_matched_controls"), "minimum matched controls", 0, 32)
    integer(contract.get("search_breadth"), "search breadth", 1, 1024)
    _text_list(contract.get("target_assets"), "target assets")
    lanes = _text_list(contract.get("downstream_lanes"), "downstream lanes", maximum=2)
    if not set(lanes) <= {"BIG_MOVE", "STRATEGY_COMPONENT"}:
        raise ValueError("unknown downstream lane")
    contract["mechanism_id"] = "mi-mechanism-" + fingerprint(key)[:24]
    contract["contract_id"] = "mi-contract-" + fingerprint(contract)[:24]
    contract.update(SAFE)
    return contract


def freeze_mechanism(spec):
    return _freeze_mechanism(spec)


def validate_mechanism(contract):
    if not isinstance(contract, dict) or set(contract) != MECHANISM_FIELDS:
        raise ValueError("mechanism contract fields mismatch")
    if any(contract.get(key) is not value for key, value in SAFE.items()):
        raise ValueError("mechanism authority violation")
    raw = {key: deepcopy(contract[key]) for key in MECHANISM_INPUT_FIELDS}
    expected = _freeze_mechanism(raw)
    if expected != contract:
        raise ValueError("mechanism identity mismatch")
    return contract


def _evidence_identity(payload):
    return {
        key: payload[key]
        for key in sorted(EVIDENCE_INPUT_FIELDS - {"narrative_summary"})
    }


def make_evidence(contract, spec):
    validate_mechanism(contract)
    if not isinstance(spec, dict) or not set(spec) <= EVIDENCE_INPUT_FIELDS:
        raise ValueError("unexpected evidence fields")
    missing = EVIDENCE_INPUT_FIELDS - set(spec)
    if missing - {"matched_control", "narrative_summary"}:
        raise ValueError("evidence fields missing")
    payload = {key: deepcopy(spec.get(key)) for key in EVIDENCE_INPUT_FIELDS}
    payload["mechanism_id"] = contract["mechanism_id"]
    payload.update(SAFE)
    payload["evidence_id"] = "mi-evidence-" + fingerprint(_evidence_identity(payload))[:24]
    validate_evidence(payload, contract=contract)
    return payload


def validate_evidence(payload, *, contract=None):
    if not isinstance(payload, dict) or set(payload) != EVIDENCE_FIELDS:
        raise ValueError("unexpected evidence fields")
    if payload.get("schema_version") != 1 or any(payload.get(key) is not value for key, value in SAFE.items()):
        raise ValueError("evidence schema or authority violation")
    if payload.get("evidence_kind") not in EVIDENCE_KINDS:
        raise ValueError("unknown evidence kind")
    observed = timestamp(payload.get("observed_at"))
    published = timestamp(payload.get("published_at"))
    available = timestamp(payload.get("available_at"))
    cutoff = timestamp(payload.get("information_cutoff"))
    if not observed <= published <= available <= cutoff:
        raise ValueError("evidence exceeds information cutoff or chronology")
    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != {"publisher", "uri", "source_type"}:
        raise ValueError("source provenance required")
    text(source.get("publisher"), "publisher")
    _validate_url(source.get("uri"))
    if source.get("source_type") not in {"PRIMARY", "OFFICIAL_DATA", "AUDITED", "RESEARCH"}:
        raise ValueError("unsupported source type")
    text(payload.get("independence_key"), "independence key")
    strength = number(payload.get("strength"), "evidence strength", minimum=0)
    if strength > 1:
        raise ValueError("evidence strength above one")
    fact = payload.get("structured_fact")
    if not isinstance(fact, dict) or not fact:
        raise ValueError("structured fact required")
    canonical(fact)
    narrative = payload.get("narrative_summary")
    if narrative is not None:
        text(narrative, "narrative summary")
    matched = payload.get("matched_control")
    needs_control = payload["evidence_kind"].startswith("MATCHED_CONTROL")
    if needs_control:
        if not isinstance(matched, dict) or set(matched) != {"control_id", "outcome", "predeclared"}:
            raise ValueError("matched control record required")
        text(matched.get("control_id"), "control id")
        expected = "SUPPORTS" if payload["evidence_kind"] == "MATCHED_CONTROL_SUPPORT" else "CONTRADICTS"
        if matched.get("outcome") != expected or matched.get("predeclared") is not True:
            raise ValueError("matched control outcome mismatch")
    elif matched is not None:
        raise ValueError("matched control attached to non-control evidence")
    if contract is not None:
        validate_mechanism(contract)
        if payload.get("mechanism_id") != contract["mechanism_id"]:
            raise ValueError("evidence mechanism mismatch")
        if timestamp(contract["frozen_at"]) > observed:
            raise ValueError("mechanism must be frozen before evidence")
    expected_id = "mi-evidence-" + fingerprint(_evidence_identity(payload))[:24]
    if payload.get("evidence_id") != expected_id:
        raise ValueError("evidence identity mismatch")
    return payload

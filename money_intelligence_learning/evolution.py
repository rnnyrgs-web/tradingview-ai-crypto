"""Deterministic confidence updating with contradictions and explicit decay."""

from __future__ import annotations

from math import pow

from profitability_learning.contracts import timestamp

from .contracts import validate_evidence, validate_mechanism


DELTAS = {
    "SUPPORT": 0.25,
    "REVALIDATION": 0.15,
    "MATCHED_CONTROL_SUPPORT": 0.20,
    "CONTRADICTION": -0.25,
    "MATCHED_CONTROL_FAILURE": -0.25,
}


def evolve_mechanism(contract, evidence, *, as_of):
    validate_mechanism(contract)
    now = timestamp(as_of)
    rows = sorted(list(evidence), key=lambda row: (timestamp(row["available_at"]), row["evidence_id"]))
    independence = set()
    raw = float(contract["prior_confidence"])
    support_count = contradiction_count = matched_control_count = 0
    source_publishers = set()
    for row in rows:
        validate_evidence(row, contract=contract)
        if timestamp(row["available_at"]) > now:
            raise ValueError("future evidence unavailable as of state time")
        key = row["independence_key"]
        if key in independence:
            raise ValueError("duplicate independence key")
        independence.add(key)
        kind = row["evidence_kind"]
        raw += DELTAS[kind] * float(row["strength"])
        if DELTAS[kind] > 0:
            support_count += 1
            source_publishers.add(row["source"]["publisher"])
        else:
            contradiction_count += 1
        if kind.startswith("MATCHED_CONTROL"):
            matched_control_count += 1
    raw = max(0.0, min(1.0, raw))
    prior = float(contract["prior_confidence"])
    decay_applied = False
    age_days = None
    confidence = raw
    if rows:
        latest = max(timestamp(row["available_at"]) for row in rows)
        age_days = max(0.0, (now - latest).total_seconds() / 86400.0)
        if age_days > 0:
            decay_applied = True
            confidence = prior + (raw - prior) * pow(0.5, age_days / contract["decay_half_life_days"])
    confidence = round(max(0.0, min(1.0, confidence)), 12)
    enough_support = len(source_publishers) >= contract["minimum_supporting_sources"]
    enough_controls = matched_control_count >= contract["minimum_matched_controls"]
    if rows and age_days is not None and age_days >= contract["decay_half_life_days"]:
        status = "STALE"
    elif contradiction_count and confidence <= prior:
        status = "CONTRADICTED"
    elif confidence >= 0.70 and enough_support and enough_controls:
        status = "SUPPORTED"
    elif confidence > prior:
        status = "PROMISING"
    else:
        status = "HYPOTHESIS"
    return {
        "mechanism_id": contract["mechanism_id"],
        "contract_id": contract["contract_id"],
        "as_of": now.isoformat(),
        "status": status,
        "prior_confidence": prior,
        "raw_confidence": round(raw, 12),
        "confidence": confidence,
        "support_count": support_count,
        "supporting_source_count": len(source_publishers),
        "contradiction_count": contradiction_count,
        "matched_control_count": matched_control_count,
        "decay_applied": decay_applied,
        "evidence_age_days": None if age_days is None else round(age_days, 12),
        "evidence_ids": [row["evidence_id"] for row in rows],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
    }

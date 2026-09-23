"""Deterministic subject identity for prospective 2x feature evidence.

This module is deliberately outcome-blind. It binds an already-authenticated feature
record digest to the exact research subject that the record is allowed to describe.
It grants no receipt trust, candidate/formation/ranking/prediction authority, broker
access, or trading authority. Callers must independently authenticate the resulting
binding before treating it as trusted subject evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SUBJECT_BINDING_SCHEMA = "two_x_feature_subject_binding.v1"
SCOPE_GLOBAL = "GLOBAL"
SCOPE_ASSET = "ASSET"
SCOPE_ASSET_VENUE_INSTRUMENT = "ASSET_VENUE_INSTRUMENT"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/+-]{1,128}$")

# Scope is frozen per v1 feature family. GLOBAL is intentionally exceptional:
# only market_regime may be reused across assets. Venue/instrument scope is used
# only when the current snapshot schema can actually name the venue/instrument.
FEATURE_SUBJECT_SCOPE = {
    "stable_identity": SCOPE_ASSET,
    "venue_membership": SCOPE_ASSET_VENUE_INSTRUMENT,
    "liquidity_proxy": SCOPE_ASSET,
    "strict_tradability": SCOPE_ASSET_VENUE_INSTRUMENT,
    "spot_participation_flow": SCOPE_ASSET,
    "leverage_state": SCOPE_ASSET,
    "supply_float": SCOPE_ASSET,
    "catalyst_state": SCOPE_ASSET,
    "market_regime": SCOPE_GLOBAL,
    "relationship_graph": SCOPE_ASSET,
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _token(value: Any, field: str) -> str:
    if not isinstance(value, str) or SAFE_TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a bounded safe token")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be lowercase SHA-256")
    return value


def _canonical_venue_symbols(value: Mapping[str, str] | None) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value or len(value) > 32:
        raise ValueError("venue_symbols must be a non-empty bounded mapping")
    canonical: dict[str, str] = {}
    for venue, instrument in value.items():
        v = _token(venue, "venue")
        symbol = _token(instrument, "instrument")
        if v in canonical:
            raise ValueError("duplicate canonical venue")
        canonical[v] = symbol
    return {key: canonical[key] for key in sorted(canonical)}


def feature_subject_scope(feature_family: str) -> str:
    family = _token(feature_family, "feature_family")
    try:
        return FEATURE_SUBJECT_SCOPE[family]
    except KeyError as exc:
        raise ValueError(f"unsupported feature family for subject binding: {family}") from exc


def feature_subject_binding_payload(
    *,
    feature_family: str,
    feature_record_sha256: str,
    asset_id: str | None = None,
    venue_symbols: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the exact canonical subject-binding payload for one feature record.

    The payload binds only identity. Trust is intentionally out of band: a caller may
    compute this digest locally, but it counts as trusted only when an independent
    trusted receipt/attestation has authenticated the same digest.
    """

    family = _token(feature_family, "feature_family")
    record_sha = _sha256(feature_record_sha256, "feature_record_sha256")
    scope = feature_subject_scope(family)
    payload: dict[str, Any] = {
        "schema": SUBJECT_BINDING_SCHEMA,
        "scope": scope,
        "feature_family": family,
        "feature_record_sha256": record_sha,
    }

    if scope == SCOPE_GLOBAL:
        if asset_id is not None or venue_symbols is not None:
            raise ValueError("GLOBAL subject binding must not carry asset or venue identity")
        return payload

    payload["asset_id"] = _token(asset_id, "asset_id")
    if scope == SCOPE_ASSET:
        if venue_symbols is not None:
            raise ValueError("ASSET subject binding must not carry venue identity")
        return payload

    if scope == SCOPE_ASSET_VENUE_INSTRUMENT:
        payload["venue_symbols"] = _canonical_venue_symbols(venue_symbols)
        return payload

    raise AssertionError("unreachable subject scope")


def feature_subject_binding_sha256(
    *,
    feature_family: str,
    feature_record_sha256: str,
    asset_id: str | None = None,
    venue_symbols: Mapping[str, str] | None = None,
) -> str:
    return hashlib.sha256(
        _canonical(
            feature_subject_binding_payload(
                feature_family=feature_family,
                feature_record_sha256=feature_record_sha256,
                asset_id=asset_id,
                venue_symbols=venue_symbols,
            )
        )
    ).hexdigest()


def expected_subject_binding_sha256(
    *,
    feature_family: str,
    feature_record_sha256: str,
    asset_id: str,
    venue_symbols: Mapping[str, str],
) -> str:
    """Convenience boundary for a feature embedded in one snapshot asset.

    GLOBAL families intentionally discard the enclosing asset identity; ASSET families
    bind only the canonical asset; ASSET_VENUE_INSTRUMENT families bind the canonical
    asset plus the full deterministic venue->instrument mapping.
    """

    scope = feature_subject_scope(feature_family)
    if scope == SCOPE_GLOBAL:
        return feature_subject_binding_sha256(
            feature_family=feature_family,
            feature_record_sha256=feature_record_sha256,
        )
    if scope == SCOPE_ASSET:
        return feature_subject_binding_sha256(
            feature_family=feature_family,
            feature_record_sha256=feature_record_sha256,
            asset_id=asset_id,
        )
    return feature_subject_binding_sha256(
        feature_family=feature_family,
        feature_record_sha256=feature_record_sha256,
        asset_id=asset_id,
        venue_symbols=venue_symbols,
    )

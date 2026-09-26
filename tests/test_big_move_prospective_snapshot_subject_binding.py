from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from big_move_prospective_snapshot import evaluate_snapshot


# Reuse the already-reviewed synthetic fixture without duplicating a large record
# construction surface in this adversarial regression file.
_FIXTURE_PATH = Path(__file__).with_name("test_big_move_prospective_snapshot.py")
_SPEC = importlib.util.spec_from_file_location("_prospective_snapshot_fixture", _FIXTURE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_FIXTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURE)


def _evaluate(snapshot):
    return evaluate_snapshot(
        _FIXTURE._contract(),
        snapshot,
        verified_receipt_sha256s=_FIXTURE.VERIFIED,
        verified_strict_derivation_sha256s={_FIXTURE._derivation_sha(snapshot)},
    )


def test_asset_a_evidence_cannot_be_transplanted_to_asset_b() -> None:
    """Internally valid evidence must still bind the enclosing canonical asset."""
    snapshot = _FIXTURE._snapshot()
    asset = snapshot["assets"][0]

    # Only the enclosing asset identity changes. The frozen feature records still
    # describe/authenticate asset:test. Today that transplant is accepted because
    # generic record validation has no enclosing subject identity.
    asset["asset_id"] = "asset:other"

    with pytest.raises(ValueError, match="subject|asset|stable_identity"):
        _evaluate(snapshot)


def test_venue_instrument_evidence_cannot_survive_symbol_transplant() -> None:
    """Venue/instrument-bound microstructure evidence must not replay elsewhere."""
    snapshot = _FIXTURE._snapshot()
    asset = snapshot["assets"][0]

    # Keep the same asset but transplant the enclosing venue/symbol while reusing
    # the same authenticated strict-tradability and venue evidence. A future
    # generic ASSET_VENUE_INSTRUMENT scope must reject this replay.
    asset["venue_symbols"] = {"COINBASE_SPOT": "TEST-USD"}

    with pytest.raises(ValueError, match="subject|venue|instrument|symbol"):
        _evaluate(snapshot)

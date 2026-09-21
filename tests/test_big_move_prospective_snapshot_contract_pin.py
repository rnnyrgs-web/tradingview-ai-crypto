import copy
import json
from pathlib import Path

import pytest

from big_move_prospective_snapshot import (
    PROSPECTIVE_CONTRACT_CANONICAL_SHA256,
    digest,
    evaluate_snapshot,
    validate_contract,
)

CONTRACT_PATH = Path("money_intelligence/2x_prospective_snapshot_contract_v1.json")


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def test_canonical_contract_digest_is_exactly_pinned():
    contract = _contract()
    validate_contract(contract)
    assert digest(contract) == PROSPECTIVE_CONTRACT_CANONICAL_SHA256


@pytest.mark.parametrize(
    "mutator",
    [
        lambda c: c.__setitem__("mandatory_for_mechanism_review", ["strict_tradability"]),
        lambda c: c["freshness_max_age_seconds"].__setitem__("venue_membership", 86400),
        lambda c: c["snapshot_semantics"].__setitem__(
            "selection_policy",
            "weakened caller-authored readiness policy",
        ),
        lambda c: c["strict_tradability_binding"].__setitem__(
            "rule",
            "caller-authored replacement rule",
        ),
    ],
)
def test_behavior_driving_contract_mutation_fails_before_snapshot_evaluation(mutator):
    contract = copy.deepcopy(_contract())
    mutator(contract)
    with pytest.raises(ValueError, match="frozen canonical artifact"):
        evaluate_snapshot(contract, {})


def test_validate_contract_rejects_same_identity_with_weaker_mandatory_set():
    contract = copy.deepcopy(_contract())
    contract["mandatory_for_mechanism_review"] = ["strict_tradability"]
    assert contract["schema"] == "two_x_prospective_snapshot_contract.v1"
    assert contract["artifact_id"] == "2X-PROSPECTIVE-SNAPSHOT-001-v1"
    with pytest.raises(ValueError, match="frozen canonical artifact"):
        validate_contract(contract)

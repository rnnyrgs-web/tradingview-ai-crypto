import json

import pytest

from orchestration.protected_paths import is_protected
from orchestration.resource_recommendations import (
    is_approved,
    load_decisions,
    load_proposals,
    unresolved_proposal_ids,
)


def test_seed_proposal_has_required_fields_and_is_unapproved():
    proposals = load_proposals()
    assert len(proposals) >= 1
    ids = {p["id"] for p in proposals}
    assert "RESOURCE-REC-001" in ids
    for proposal in proposals:
        for field in ("id", "proposed_by", "proposed_at", "cost", "limitation_solved", "expected_benefit", "free_alternatives_considered", "evidence"):
            assert field in proposal, (proposal["id"], field)
    assert is_approved("RESOURCE-REC-001") is False


def test_decisions_file_starts_empty():
    assert load_decisions() == []


def test_unresolved_proposal_ids_includes_seed_proposal_until_decided():
    unresolved = unresolved_proposal_ids()
    assert "RESOURCE-REC-001" in unresolved


def test_is_approved_only_true_after_matching_approved_decision():
    decisions = [{"proposal_id": "RESOURCE-REC-001", "decision": "APPROVED", "decided_by": "user", "decided_at": "2026-09-14", "rationale": "ok"}]
    assert is_approved("RESOURCE-REC-001", decisions) is True
    assert is_approved("RESOURCE-REC-999", decisions) is False
    rejected = [{"proposal_id": "RESOURCE-REC-001", "decision": "REJECTED", "decided_by": "user", "decided_at": "2026-09-14", "rationale": "no"}]
    assert is_approved("RESOURCE-REC-001", rejected) is False


def test_invalid_decision_value_is_rejected(tmp_path):
    bad = {"decisions": [{"proposal_id": "X", "decision": "MAYBE", "decided_by": "u", "decided_at": "d", "rationale": "r"}]}
    path = tmp_path / "bad_decisions.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="decision must be one of"):
        load_decisions(path)


def test_decisions_file_is_a_protected_path_no_engine_can_write():
    assert is_protected("resource_recommendations_decisions.json")


def test_proposed_file_is_not_protected_so_engines_can_be_granted_access():
    assert not is_protected("resource_recommendations_proposed.json")


def test_no_engine_role_allowlist_includes_the_decisions_file():
    """Cross-checks every enabled engine config's role allowlists.

    This is the concrete "resource recommendation separation" guarantee:
    even if orchestration/protected_paths.json were ever misconfigured, no
    engine's own role definition grants it access to the decisions file.
    """
    from agents.autonomous_cloud_runner import load_config as load_openai_config
    from agents.claude_specialist_runner import CONFIG_PATH as CLAUDE_CONFIG_PATH
    from agents.claude_code_specialist_runner import CONFIG_PATH as CLAUDE_CODE_CONFIG_PATH

    for config_path in (None, CLAUDE_CONFIG_PATH, CLAUDE_CODE_CONFIG_PATH):
        config = load_openai_config() if config_path is None else load_openai_config(config_path)
        for role, settings in config["roles"].items():
            assert "resource_recommendations_decisions.json" not in settings["allowed_paths"], role

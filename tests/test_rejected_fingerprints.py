import copy

import pytest

from orchestration.rejected_fingerprints import (
    is_rejected_fingerprint,
    load_rejected_fingerprints,
    rejection_record,
)
from orchestration.specialist_coordination import load_state, validate_state


def test_canonical_registry_loads_with_required_fields():
    entries = load_rejected_fingerprints()
    assert len(entries) >= 2
    ids = {e["fingerprint_id"] for e in entries}
    assert "DATA-BASIS-001" in ids
    assert "DATA-FUNDING-001" in ids
    for entry in entries:
        assert entry["do_not_resubmit_same_fingerprint"] is True
        assert entry["reconsideration_conditions"]
        assert entry["horizons_evaluated"]
        assert entry["sample_sizes"]
        assert entry["rejection_evidence"]


def test_is_rejected_fingerprint_exact_match_only():
    assert is_rejected_fingerprint("DATA-BASIS-001") is True
    assert is_rejected_fingerprint("DATA-FUNDING-001") is True
    # A genuinely different hypothesis must not be barred merely because its
    # name resembles a rejected one (prefix/substring match is not enough).
    assert is_rejected_fingerprint("DATA-BASIS-002") is False
    assert is_rejected_fingerprint("DATA-BASIS-001-V2") is False
    assert is_rejected_fingerprint("DATA-FUNDING") is False
    assert is_rejected_fingerprint("UNRELATED-CANDIDATE") is False


def test_rejection_record_returns_full_evidence():
    record = rejection_record("DATA-BASIS-001")
    assert record is not None
    assert record["rejection_pr"] == 291
    assert record["rejection_evidence"]["24h_avg_net_bps"] == pytest.approx(-8.490253160921695)


def test_duplicate_fingerprint_id_is_rejected(tmp_path):
    import json

    entries = load_rejected_fingerprints()
    duplicated = {"entries": [entries[0], copy.deepcopy(entries[0])]}
    path = tmp_path / "duplicate_registry.json"
    path.write_text(json.dumps(duplicated), encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicate rejected fingerprint"):
        load_rejected_fingerprints(path)


def test_missing_required_field_is_rejected(tmp_path):
    import json

    bad = {"entries": [{"fingerprint_id": "X", "do_not_resubmit_same_fingerprint": True}]}
    path = tmp_path / "bad_registry.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing fields"):
        load_rejected_fingerprints(path)


def test_coordination_task_declaring_rejected_fingerprint_fails_closed():
    state = load_state()
    bad = copy.deepcopy(state)
    task = bad["tasks"][0]
    task["fingerprint_id"] = "DATA-BASIS-001"
    task["status"] = "READY"
    with pytest.raises(RuntimeError, match="rejected fingerprint"):
        validate_state(bad)


def test_coordination_task_declaring_rejected_fingerprint_is_fine_when_done():
    # A DONE task recording historical rejection evidence (as
    # COORD-DATA-003/004 already do via completion_evidence.candidate_id,
    # not this new field) must not be blocked -- the check only fires for
    # active statuses, since it exists to stop *reopening* rejected work.
    state = load_state()
    ok = copy.deepcopy(state)
    task = ok["tasks"][0]
    task["fingerprint_id"] = "DATA-BASIS-001"
    task["status"] = "DONE"
    validate_state(ok)  # must not raise


def test_coordination_task_with_genuinely_new_fingerprint_is_unaffected():
    state = load_state()
    ok = copy.deepcopy(state)
    task = ok["tasks"][0]
    task["fingerprint_id"] = "DATA-BREADTH-002-GENUINELY-NEW"
    task["status"] = "READY"
    task["work_mode"] = "CHEAP_SCREEN"
    validate_state(ok)  # must not raise

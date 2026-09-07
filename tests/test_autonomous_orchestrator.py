from agents.autonomous_orchestrator import extract_json, normalize_relpath, path_allowed
from agents.autonomous_worker import _completion_text


def test_role_path_allowlists_are_fail_closed():
    assert path_allowed("quant-research", "strategy_families.py")
    assert path_allowed("data-market", "market_data.py")
    assert path_allowed("production-risk", "safety.py")
    assert not path_allowed("quant-research", "market_data.py")
    assert not path_allowed("data-market", "engine.py")


def test_protected_paths_are_never_specialist_writable():
    for role in (
        "quant-research",
        "data-market",
        "strategy-registry",
        "production-risk",
        "testing-security",
    ):
        assert not path_allowed(role, "AI_STATE.md")
        assert not path_allowed(role, "agents/autonomous_orchestrator.py")
        assert not path_allowed(role, ".github/workflows/security.yml")
        assert not path_allowed(role, "requirements.txt")
        assert not path_allowed(role, "Dockerfile")


def test_path_traversal_is_rejected():
    assert not path_allowed("testing-security", "../AI_STATE.md")
    assert not path_allowed("testing-security", "/tmp/test.py")


def test_normalize_relpath_rejects_empty_and_parent_paths():
    for unsafe in ("", "../x", "a/../../x", "/etc/passwd"):
        try:
            normalize_relpath(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe path accepted: {unsafe}")


def test_extract_json_accepts_plain_and_fenced_json():
    assert extract_json('{"approve": true}') == {"approve": True}
    assert extract_json('```json\n{"approve": false}\n```') == {"approve": False}


def test_worker_completion_marker_is_required():
    payload = {"output_text": "done"}
    try:
        _completion_text(payload)
    except RuntimeError:
        pass
    else:
        raise AssertionError("worker accepted completion without CHANGE_STATUS")


def test_worker_accepts_explicit_ready_or_no_change_markers():
    assert "READY_FOR_PR" in _completion_text({"output_text": "CHANGE_STATUS: READY_FOR_PR"})
    assert "NO_CHANGE" in _completion_text({"output_text": "CHANGE_STATUS: NO_CHANGE"})

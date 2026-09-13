import json

import pytest

from orchestration.architecture_review_backlog import load_backlog, open_items


def test_backlog_loads_with_required_fields():
    items = load_backlog()
    assert len(items) >= 10
    for item in items:
        for field in ("id", "severity", "summary", "evidence", "status"):
            assert item.get(field), (item.get("id"), field)


def test_protect_path_001_is_recorded_as_fixed_with_a_reference():
    items = load_backlog()
    fixed = next(i for i in items if i["id"] == "PROTECT-PATH-001")
    assert fixed["status"] == "FIXED"
    assert fixed["severity"] == "HIGH"
    assert fixed["fixed_in"]


def test_open_items_excludes_fixed_items():
    items = load_backlog()
    open_ids = {i["id"] for i in open_items(items)}
    assert "PROTECT-PATH-001" not in open_ids
    assert len(open_ids) >= 9


def test_invalid_severity_is_rejected(tmp_path):
    from orchestration.architecture_review_backlog import load_backlog as loader

    bad = {"items": [{"id": "X", "severity": "CRITICAL", "summary": "s", "evidence": "e", "status": "OPEN"}]}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid severity"):
        loader(path)


def test_fixed_item_without_fixed_in_reference_is_rejected(tmp_path):
    from orchestration.architecture_review_backlog import load_backlog as loader

    bad = {"items": [{"id": "X", "severity": "LOW", "summary": "s", "evidence": "e", "status": "FIXED"}]}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="FIXED backlog item missing fixed_in"):
        loader(path)

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import pit_trusted_acquisition_issue_bridge as bridge


def _event(*, kind: str = "COMMONCRAWL_INDEX", body: dict | None = None) -> dict:
    if body is None:
        body = {
            "collection": "CC-MAIN-2026-34",
            "target_url": "https://example.org/project/docs?a=1",
        }
    return {
        "action": "opened",
        "repository": {
            "full_name": bridge.EXPECTED_REPOSITORY,
            "default_branch": "main",
            "owner": {"login": bridge.EXPECTED_OWNER},
        },
        "sender": {"login": bridge.EXPECTED_OWNER},
        "issue": {
            "number": 123,
            "state": "open",
            "title": f"{bridge.TITLE_PREFIX}{kind}",
            "body": json.dumps(body),
            "user": {"login": bridge.EXPECTED_OWNER},
        },
    }


def test_valid_index_request_builds_fixed_shell_free_dispatch_argv():
    issue_number, source_kind, fields = bridge.validate_event(_event())
    assert issue_number == 123
    assert source_kind == "COMMONCRAWL_INDEX"
    assert fields == {
        "source_kind": "COMMONCRAWL_INDEX",
        "collection": "CC-MAIN-2026-34",
        "target_url": "https://example.org/project/docs?a=1",
    }
    argv = bridge.build_dispatch_argv(fields)
    assert argv[:9] == [
        "gh",
        "workflow",
        "run",
        bridge.TARGET_WORKFLOW,
        "--repo",
        bridge.EXPECTED_REPOSITORY,
        "--ref",
        "main",
        "-f",
    ]
    assert "source_kind=COMMONCRAWL_INDEX" in argv
    assert "collection=CC-MAIN-2026-34" in argv
    assert "target_url=https://example.org/project/docs?a=1" in argv


def test_valid_warc_request_binds_collection_filename_and_range():
    body = {
        "collection": "CC-MAIN-2026-34",
        "filename": (
            "crawl-data/CC-MAIN-2026-34/segments/123.0/warc/"
            "CC-MAIN-20260901000000-00000.warc.gz"
        ),
        "offset": "100",
        "length": 250,
    }
    _, kind, fields = bridge.validate_event(
        _event(kind="COMMONCRAWL_WARC_RANGE", body=body)
    )
    assert kind == "COMMONCRAWL_WARC_RANGE"
    assert fields["offset"] == "100"
    assert fields["length"] == "250"
    assert fields["filename"].startswith("crawl-data/CC-MAIN-2026-34/")


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda e: e["sender"].update(login="attacker"), "repository owner"),
        (lambda e: e["issue"]["user"].update(login="attacker"), "repository owner"),
        (lambda e: e["repository"].update(full_name="attacker/fork"), "wrong repository"),
        (lambda e: e.update(action="edited"), "newly opened"),
        (lambda e: e["issue"].update(state="closed"), "must be open"),
    ],
)
def test_non_owner_or_noncanonical_issue_context_is_rejected(mutator, message):
    event = _event()
    mutator(event)
    with pytest.raises(bridge.BridgeRequestError, match=message):
        bridge.validate_event(event)


def test_index_request_rejects_extra_keys_and_non_https_url():
    extra = _event()
    payload = json.loads(extra["issue"]["body"])
    payload["available_at"] = "2021-01-01T00:00:00Z"
    extra["issue"]["body"] = json.dumps(payload)
    with pytest.raises(bridge.BridgeRequestError, match="keys must be exactly"):
        bridge.validate_event(extra)

    insecure = _event(
        body={
            "collection": "CC-MAIN-2026-34",
            "target_url": "http://example.org/project/docs",
        }
    )
    with pytest.raises(bridge.BridgeRequestError, match="clean HTTPS"):
        bridge.validate_event(insecure)


def test_warc_request_rejects_cross_collection_traversal_and_oversized_range():
    cross_collection = _event(
        kind="COMMONCRAWL_WARC_RANGE",
        body={
            "collection": "CC-MAIN-2026-34",
            "filename": "crawl-data/CC-MAIN-2025-30/segments/1/warc/x.warc.gz",
            "offset": 0,
            "length": 100,
        },
    )
    with pytest.raises(bridge.BridgeRequestError, match="bound to the requested collection"):
        bridge.validate_event(cross_collection)

    traversal = _event(
        kind="COMMONCRAWL_WARC_RANGE",
        body={
            "collection": "CC-MAIN-2026-34",
            "filename": "crawl-data/CC-MAIN-2026-34/../secret/x.warc.gz",
            "offset": 0,
            "length": 100,
        },
    )
    with pytest.raises(bridge.BridgeRequestError, match="bound to the requested collection"):
        bridge.validate_event(traversal)

    oversized = _event(
        kind="COMMONCRAWL_WARC_RANGE",
        body={
            "collection": "CC-MAIN-2026-34",
            "filename": "crawl-data/CC-MAIN-2026-34/segments/1/warc/x.warc.gz",
            "offset": 0,
            "length": bridge.MAX_RANGE_BYTES + 1,
        },
    )
    with pytest.raises(bridge.BridgeRequestError, match="length out of bounds"):
        bridge.validate_event(oversized)


def test_dispatch_uses_fixed_argv_without_shell_and_records_marker(monkeypatch):
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        if argv[:3] == ["gh", "issue", "view"]:
            return SimpleNamespace(stdout=json.dumps({"state": "OPEN", "comments": []}))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    argv = bridge.dispatch(_event(), env={"GH_TOKEN": "test-token"})

    assert argv[0:4] == ["gh", "workflow", "run", bridge.TARGET_WORKFLOW]
    assert any(call[0][0:3] == ["gh", "issue", "comment"] for call in calls)
    assert any(call[0][0:3] == ["gh", "issue", "close"] for call in calls)
    assert all("shell" not in kwargs for _, kwargs in calls)
    assert all(kwargs.get("check") is True for _, kwargs in calls)


def test_trusted_dispatch_marker_or_closed_issue_prevents_duplicate_dispatch(monkeypatch):
    for state, comments in (
        (
            "OPEN",
            [
                {
                    "author": {"login": "github-actions[bot]"},
                    "body": f"{bridge.DISPATCH_MARKER} issue=123",
                }
            ],
        ),
        ("CLOSED", []),
    ):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            return SimpleNamespace(
                stdout=json.dumps({"state": state, "comments": comments})
            )

        monkeypatch.setattr(bridge.subprocess, "run", fake_run)
        assert bridge.dispatch(_event(), env={"GH_TOKEN": "test-token"}) == []
        assert len(calls) == 1
        assert calls[0][:3] == ["gh", "issue", "view"]


def test_public_comment_cannot_spoof_dispatch_marker(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if argv[:3] == ["gh", "issue", "view"]:
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "state": "OPEN",
                        "comments": [
                            {
                                "author": {"login": "attacker"},
                                "body": f"{bridge.DISPATCH_MARKER} issue=123",
                            }
                        ],
                    }
                )
            )
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    assert bridge.dispatch(_event(), env={"GH_TOKEN": "test-token"})
    assert any(call[:3] == ["gh", "workflow", "run"] for call in calls)

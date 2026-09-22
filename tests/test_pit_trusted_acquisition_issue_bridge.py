from __future__ import annotations

import json

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


def test_valid_index_request_builds_frozen_dispatch_payload():
    issue_number, source_kind, fields = bridge.validate_event(_event())
    assert issue_number == 123
    assert source_kind == "COMMONCRAWL_INDEX"
    assert fields == {
        "source_kind": "COMMONCRAWL_INDEX",
        "collection": "CC-MAIN-2026-34",
        "target_url": "https://example.org/project/docs?a=1",
    }
    assert bridge.build_dispatch_payload(fields) == {
        "ref": "main",
        "inputs": fields,
    }


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


def test_dispatch_uses_fixed_github_api_paths_and_records_marker(monkeypatch):
    calls: list[dict] = []

    def fake_request(method, path, *, token, payload=None, expected_status):
        calls.append(
            {
                "method": method,
                "path": path,
                "token": token,
                "payload": payload,
                "expected_status": set(expected_status),
            }
        )
        if method == "GET" and path.endswith("/issues/123"):
            return {"state": "open"}
        if method == "GET" and "/comments?" in path:
            return []
        if method == "POST" and path.endswith("/dispatches"):
            return None
        if method == "POST" and path.endswith("/comments"):
            return {"id": 1}
        if method == "PATCH" and path.endswith("/issues/123"):
            return {"state": "closed"}
        raise AssertionError((method, path))

    monkeypatch.setattr(bridge, "_github_json_request", fake_request)
    payload = bridge.dispatch(_event(), token="test-token")

    assert payload == {
        "ref": "main",
        "inputs": {
            "source_kind": "COMMONCRAWL_INDEX",
            "collection": "CC-MAIN-2026-34",
            "target_url": "https://example.org/project/docs?a=1",
        },
    }
    dispatch_calls = [c for c in calls if c["path"].endswith("/dispatches")]
    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["method"] == "POST"
    assert dispatch_calls[0]["path"] == (
        f"/repos/{bridge.EXPECTED_REPOSITORY}/actions/workflows/"
        f"{bridge.TARGET_WORKFLOW}/dispatches"
    )
    assert any(c["method"] == "POST" and c["path"].endswith("/comments") for c in calls)
    assert any(c["method"] == "PATCH" and c["path"].endswith("/issues/123") for c in calls)


def test_trusted_dispatch_marker_or_closed_issue_prevents_duplicate_dispatch(monkeypatch):
    for state, comments in (
        (
            "open",
            [
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": f"{bridge.DISPATCH_MARKER} issue=123",
                }
            ],
        ),
        ("closed", []),
    ):
        calls = []

        def fake_request(method, path, *, token, payload=None, expected_status):
            calls.append((method, path))
            if path.endswith("/issues/123"):
                return {"state": state}
            if "/comments?" in path:
                return comments
            raise AssertionError((method, path))

        monkeypatch.setattr(bridge, "_github_json_request", fake_request)
        assert bridge.dispatch(_event(), token="test-token") is None
        assert not any(path.endswith("/dispatches") for _, path in calls)


def test_public_comment_cannot_spoof_dispatch_marker(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_request(method, path, *, token, payload=None, expected_status):
        calls.append((method, path))
        if method == "GET" and path.endswith("/issues/123"):
            return {"state": "open"}
        if method == "GET" and "/comments?" in path:
            return [
                {
                    "user": {"login": "attacker"},
                    "body": f"{bridge.DISPATCH_MARKER} issue=123",
                }
            ]
        if method == "POST" and path.endswith("/dispatches"):
            return None
        if method == "POST" and path.endswith("/comments"):
            return {"id": 1}
        if method == "PATCH" and path.endswith("/issues/123"):
            return {"state": "closed"}
        raise AssertionError((method, path))

    monkeypatch.setattr(bridge, "_github_json_request", fake_request)
    assert bridge.dispatch(_event(), token="test-token") is not None
    assert any(path.endswith("/dispatches") for _, path in calls)


def test_github_api_path_escape_is_rejected_before_network():
    with pytest.raises(bridge.BridgeRequestError, match="repository boundary"):
        bridge._github_json_request(
            "GET",
            "/repos/attacker/fork/issues/1",
            token="test-token",
            expected_status={200},
        )

from __future__ import annotations

import base64
import copy
from pathlib import Path

import pytest

from orchestration.review_scope_policy import REVIEW_RECEIPT_SCHEMA_VERSION
from orchestration import reviewer_trust_root as trust


RUNTIME_SHA = "c" * 40
REPO = "rnnyrgs-web/tradingview-ai-crypto"
WORKFLOW_PATH = ".github/workflows/exact_head_independent_review.yml"
WORKFLOW_REF = f"{REPO}/{WORKFLOW_PATH}@refs/heads/main"
EXPECTED_WORKFLOW_BLOB = "6ff73beae3f3859418fb30ca941c8be8a8bc1824"


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_RUN_ID": "123456789",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_EVENT_NAME": "issues",
        "GITHUB_WORKFLOW_REF": WORKFLOW_REF,
        "GITHUB_WORKFLOW_SHA": RUNTIME_SHA,
        "GITHUB_SHA": RUNTIME_SHA,
        "GITHUB_REF": "refs/heads/main",
        "GH_TOKEN": "attacker-controlled-token",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _server_run() -> dict:
    return {
        "id": 123456789,
        "repository": {"full_name": REPO},
        "path": WORKFLOW_PATH,
        "event": "issues",
        "run_attempt": 2,
        "head_branch": "main",
        "head_sha": RUNTIME_SHA,
    }


def _server_main() -> dict:
    return {"object": {"sha": RUNTIME_SHA}}


def _server_workflow() -> dict:
    raw = Path(WORKFLOW_PATH).read_bytes()
    assert trust._git_blob_sha(raw) == EXPECTED_WORKFLOW_BLOB
    return {
        "type": "file",
        "encoding": "base64",
        "sha": EXPECTED_WORKFLOW_BLOB,
        "content": base64.b64encode(raw).decode("ascii"),
    }


def _patch_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_api(url: str) -> dict:
        if "/actions/runs/" in url:
            return _server_run()
        if url.endswith("/git/ref/heads/main"):
            return _server_main()
        if f"/contents/{WORKFLOW_PATH}?ref={RUNTIME_SHA}" in url:
            return _server_workflow()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(trust, "_github_public_api_json", fake_api)


def _context(monkeypatch: pytest.MonkeyPatch) -> dict:
    _env(monkeypatch)
    _patch_api(monkeypatch)
    return trust.collect_trusted_workflow_context(runtime_git_sha=RUNTIME_SHA)


def _base_receipt(approve: bool = True) -> dict:
    return {
        "review_receipt_schema_version": REVIEW_RECEIPT_SCHEMA_VERSION,
        "review_context_sha256": "a" * 64,
        "approve": approve,
        "risk": "low",
        "reason": "bounded exact-head review",
        "integration_authority": "NONE",
    }


def test_machine_readable_trust_root_identity_is_stable() -> None:
    root = trust.load_reviewer_trust_root()
    assert root["required_runner_environment"] == "github-hosted"
    assert root["workflow_source"] == {
        "git_blob_sha": EXPECTED_WORKFLOW_BLOB,
        "binding": "git_blob_sha_plus_runtime_sha256",
    }
    assert root["parent_trust_root"] == {
        "schema_version": 1,
        "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V1",
        "sha256": "53c96f8eca58aba2f5242c858c766b5b4ca65d93839aa9734338ee3de0aebe3f",
    }
    assert root["authority"]["approval_receipt_grants_integration"] is False
    assert root["authority"]["integration_authority"] == "NONE"
    assert "GitHub.com control-plane compromise" in root["out_of_scope_platform_compromise"]
    assert trust.reviewer_trust_root_identity() == {
        "schema_version": 2,
        "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V2",
        "sha256": "5cf45d9cd44a8728ecd894fcfc1d79d9f43c0dfb24a579ed688dc5f800ec86dc",
    }


def test_trusted_context_reconciles_env_with_public_server_and_workflow_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(monkeypatch)
    assert context["run_id"] == 123456789
    assert context["run_attempt"] == 2
    assert context["event_name"] == "issues"
    assert context["workflow_sha"] == RUNTIME_SHA
    assert context["server_run_head_sha"] == RUNTIME_SHA
    assert context["server_main_sha"] == RUNTIME_SHA
    assert context["local_workflow_blob_sha"] == EXPECTED_WORKFLOW_BLOB
    assert context["server_workflow_blob_sha"] == EXPECTED_WORKFLOW_BLOB
    assert context["local_workflow_sha256"] == context["server_workflow_sha256"]
    assert context["server_observation_auth"] == "PUBLIC_UNAUTHENTICATED_GITHUB_API"
    assert len(trust.workflow_trust_context_sha256(context)) == 64


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_trusted_context_accepts_github_line_wrapped_workflow_source(
    monkeypatch: pytest.MonkeyPatch, line_ending: str
) -> None:
    _env(monkeypatch)

    def fake_api(url: str) -> dict:
        if "/actions/runs/" in url:
            return _server_run()
        if url.endswith("/git/ref/heads/main"):
            return _server_main()
        if f"/contents/{WORKFLOW_PATH}?ref={RUNTIME_SHA}" in url:
            payload = _server_workflow()
            encoded = payload["content"]
            payload["content"] = line_ending.join(
                encoded[index : index + 60] for index in range(0, len(encoded), 60)
            )
            return payload
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(trust, "_github_public_api_json", fake_api)
    context = trust.collect_trusted_workflow_context(runtime_git_sha=RUNTIME_SHA)
    assert context["server_workflow_blob_sha"] == EXPECTED_WORKFLOW_BLOB


@pytest.mark.parametrize("separator", [" ", "\t", "#"])
def test_server_workflow_base64_rejects_non_line_wrapping(separator: str) -> None:
    payload = _server_workflow()
    encoded = payload["content"]
    payload["content"] = encoded[:60] + separator + encoded[60:]

    with pytest.raises(RuntimeError, match="server workflow source base64 invalid"):
        trust._server_workflow_bytes(payload)


def test_public_server_observation_does_not_send_workflow_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True}

    def fake_get(url: str, *, headers: dict, timeout: float, follow_redirects: bool):
        assert url == "https://api.github.com/example"
        assert "Authorization" not in headers
        assert timeout == 10.0
        assert follow_redirects is False
        return FakeResponse()

    monkeypatch.setenv("GH_TOKEN", "attacker-controlled-token")
    monkeypatch.setenv("GITHUB_TOKEN", "another-attacker-controlled-token")
    monkeypatch.setattr(trust.httpx, "get", fake_get)
    assert trust._github_public_api_json("https://api.github.com/example") == {"ok": True}


@pytest.mark.parametrize(
    ("env_key", "env_value", "message"),
    [
        ("RUNNER_ENVIRONMENT", "self-hosted", "trusted runner class"),
        ("GITHUB_RUN_ATTEMPT", "3", "run attempt mismatch"),
        ("GITHUB_EVENT_NAME", "pull_request", "untrusted review workflow event"),
        ("GITHUB_WORKFLOW_SHA", "d" * 40, "workflow SHA does not match reviewer runtime"),
        ("GITHUB_SHA", "d" * 40, "GitHub SHA does not match reviewer runtime"),
    ],
)
def test_trusted_context_rejects_environment_or_server_replay(
    monkeypatch: pytest.MonkeyPatch, env_key: str, env_value: str, message: str
) -> None:
    _env(monkeypatch)
    _patch_api(monkeypatch)
    monkeypatch.setenv(env_key, env_value)
    with pytest.raises(RuntimeError, match=message):
        trust.collect_trusted_workflow_context(runtime_git_sha=RUNTIME_SHA)


def test_trusted_context_rejects_server_main_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)

    def fake_api(url: str) -> dict:
        if "/actions/runs/" in url:
            return _server_run()
        if url.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "d" * 40}}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(trust, "_github_public_api_json", fake_api)
    with pytest.raises(RuntimeError, match="canonical main advanced"):
        trust.collect_trusted_workflow_context(runtime_git_sha=RUNTIME_SHA)


def test_trusted_context_rejects_server_workflow_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)

    def fake_api(url: str) -> dict:
        if "/actions/runs/" in url:
            return _server_run()
        if url.endswith("/git/ref/heads/main"):
            return _server_main()
        if "/contents/" in url:
            payload = _server_workflow()
            payload["sha"] = "d" * 40
            return payload
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(trust, "_github_public_api_json", fake_api)
    with pytest.raises(RuntimeError, match="server review workflow source drifted"):
        trust.collect_trusted_workflow_context(runtime_git_sha=RUNTIME_SHA)


def test_approval_consumer_distinguishes_integrity_from_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch)
    rejected = trust.seal_review_receipt_trust(_base_receipt(approve=False), trusted_context=context)
    trust.verify_trust_bound_review_receipt(
        rejected,
        trusted_context=context,
        current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
        require_approval=False,
    )
    with pytest.raises(RuntimeError, match="rejection cannot be consumed as approval"):
        trust.verify_trust_bound_review_receipt(
            rejected,
            trusted_context=context,
            current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
            require_approval=True,
        )


def test_current_approval_passes_only_current_trust_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch)
    approved = trust.seal_review_receipt_trust(_base_receipt(approve=True), trusted_context=context)
    trust.verify_trust_bound_review_receipt(
        approved,
        trusted_context=context,
        current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
        require_approval=True,
    )

    tampered = copy.deepcopy(approved)
    tampered["workflow_trust_context"]["run_attempt"] = 3
    with pytest.raises(RuntimeError, match="trusted workflow context mismatch"):
        trust.verify_trust_bound_review_receipt(
            tampered,
            trusted_context=context,
            current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
            require_approval=True,
        )


def test_v1_binding_is_historical_even_if_schema_is_manually_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(monkeypatch)
    historical = trust.seal_review_receipt_trust(_base_receipt(approve=True), trusted_context=context)
    historical["review_trust_binding_version"] = 1
    assert trust.receipt_lineage_status(
        historical, current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION
    ) == "HISTORICAL_ONLY_NOT_APPROVAL"
    with pytest.raises(RuntimeError, match="historical review receipt"):
        trust.verify_trust_bound_review_receipt(
            historical,
            trusted_context=context,
            current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
            require_approval=True,
        )


def test_historical_receipt_schema_is_never_reinterpreted_as_current_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(monkeypatch)
    historical = trust.seal_review_receipt_trust(_base_receipt(approve=True), trusted_context=context)
    historical["review_receipt_schema_version"] = REVIEW_RECEIPT_SCHEMA_VERSION - 1
    assert trust.receipt_lineage_status(
        historical, current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION
    ) == "HISTORICAL_ONLY_NOT_APPROVAL"
    with pytest.raises(RuntimeError, match="historical review receipt"):
        trust.verify_trust_bound_review_receipt(
            historical,
            trusted_context=context,
            current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
            require_approval=True,
        )


def test_workflow_consumes_verified_current_receipts_not_bare_json_booleans() -> None:
    workflow = Path(WORKFLOW_PATH).read_text(encoding="utf-8")
    assert "verify-current-receipt" in workflow
    assert "verify-current-approval" in workflow
    assert "jq -e '.approve == true and .integration_authority == \"NONE\"'" not in workflow

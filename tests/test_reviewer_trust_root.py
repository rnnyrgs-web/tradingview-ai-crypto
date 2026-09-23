from __future__ import annotations

import copy
from pathlib import Path

import pytest

from orchestration.review_scope_policy import REVIEW_RECEIPT_SCHEMA_VERSION
from orchestration import reviewer_trust_root as trust


RUNTIME_SHA = "c" * 40
REPO = "rnnyrgs-web/tradingview-ai-crypto"
WORKFLOW_PATH = ".github/workflows/exact_head_independent_review.yml"
WORKFLOW_REF = f"{REPO}/{WORKFLOW_PATH}@refs/heads/main"


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
        "GH_TOKEN": "test-token",
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


def _patch_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_api(url: str, token: str) -> dict:
        assert token == "test-token"
        if "/actions/runs/" in url:
            return _server_run()
        if url.endswith("/git/ref/heads/main"):
            return _server_main()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(trust, "_github_api_json", fake_api)


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
    assert root["authority"]["approval_receipt_grants_integration"] is False
    assert root["authority"]["integration_authority"] == "NONE"
    assert "GitHub.com control-plane compromise" in root["out_of_scope_platform_compromise"]
    assert trust.reviewer_trust_root_identity() == {
        "schema_version": 1,
        "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V1",
        "sha256": "53c96f8eca58aba2f5242c858c766b5b4ca65d93839aa9734338ee3de0aebe3f",
    }


def test_trusted_context_reconciles_env_with_server_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch)
    assert context["run_id"] == 123456789
    assert context["run_attempt"] == 2
    assert context["event_name"] == "issues"
    assert context["workflow_sha"] == RUNTIME_SHA
    assert context["server_run_head_sha"] == RUNTIME_SHA
    assert context["server_main_sha"] == RUNTIME_SHA
    assert len(trust.workflow_trust_context_sha256(context)) == 64


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

    def fake_api(url: str, token: str) -> dict:
        if "/actions/runs/" in url:
            return _server_run()
        return {"object": {"sha": "d" * 40}}

    monkeypatch.setattr(trust, "_github_api_json", fake_api)
    with pytest.raises(RuntimeError, match="canonical main advanced"):
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
    workflow = Path(".github/workflows/exact_head_independent_review.yml").read_text(encoding="utf-8")
    assert "verify-current-receipt" in workflow
    assert "verify-current-approval" in workflow
    assert "jq -e '.approve == true and .integration_authority == \"NONE\"'" not in workflow

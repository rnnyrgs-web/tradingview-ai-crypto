import hashlib
import json

import pytest

from agents.claude_code_auth import (
    SUBSCRIPTION_AUTOMATED,
    AuthPolicyError,
    make_auth_receipt,
    resolve_auth,
    validate_auth_receipt,
    validate_capability_receipt,
)


MAIN = "a" * 40
PROOF = "github-actions://rnnyrgs-web/tradingview-ai-crypto/runs/123/attempts/1"
WORKFLOW_REF = (
    "rnnyrgs-web/tradingview-ai-crypto/"
    ".github/workflows/claude_code_subscription_probe.yml@refs/heads/main"
)


def capability_receipt(**overrides):
    receipt = {
        "version": 3,
        "provider": "anthropic",
        "engine": "claude-code",
        "auth_mode": SUBSCRIPTION_AUTOMATED,
        "reason": "OFFICIAL_OAUTH_ACTION_STRUCTURED_PROBE_SUCCEEDED",
        "repository": "rnnyrgs-web/tradingview-ai-crypto",
        "run_id": "123",
        "run_attempt": "1",
        "event_name": "workflow_dispatch",
        "head_sha": MAIN,
        "execution_sha": MAIN,
        "workflow_ref": WORKFLOW_REF,
        "probe_step_outcome": "success",
        "probe_conclusion": "success",
        "structured_probe_verified": True,
        "proof_ref": PROOF,
    }
    receipt.update(overrides)
    raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["content_digest"] = hashlib.sha256(raw).hexdigest()
    return receipt


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"event_name": "pull_request"}, "workflow_dispatch"),
        (
            {
                "workflow_ref": (
                    "rnnyrgs-web/tradingview-ai-crypto/"
                    ".github/workflows/claude_code_subscription_probe.yml@refs/pull/539/merge"
                )
            },
            "workflow identity",
        ),
        ({"execution_sha": "b" * 40}, "execution SHA"),
    ],
)
def test_subscription_capability_requires_exact_trusted_main_execution(overrides, match):
    with pytest.raises(AuthPolicyError, match=match):
        validate_capability_receipt(capability_receipt(**overrides), trusted_workflow_sha=MAIN)


@pytest.mark.parametrize(
    "branch",
    [
        "main",
        "master",
        "refs/heads/main",
        "refs/heads/master",
        " main ",
        "refs/heads/main ",
    ],
)
def test_auth_receipt_rejects_direct_main_aliases_and_whitespace(branch):
    decision = resolve_auth(oauth_present=False, api_key_present=False)
    with pytest.raises(AuthPolicyError, match="main|whitespace"):
        make_auth_receipt(
            task_id="V2-004-PROBE",
            request_id="run-1",
            branch=branch,
            base_main_sha=MAIN,
            decision=decision,
            observed_at="2026-09-21T07:45:00Z",
        )


@pytest.mark.parametrize(
    "branch",
    [
        "main",
        "master",
        "refs/heads/main",
        "refs/heads/master",
        " main ",
        "refs/heads/main ",
    ],
)
def test_existing_receipt_validation_rejects_direct_main_aliases_and_whitespace(branch):
    decision = resolve_auth(oauth_present=False, api_key_present=False)
    receipt = make_auth_receipt(
        task_id="V2-004-PROBE",
        request_id="run-1",
        branch="auto/testing-security/v2-004-probe",
        base_main_sha=MAIN,
        decision=decision,
        observed_at="2026-09-21T07:45:00Z",
    )
    tampered = dict(receipt)
    tampered["branch"] = branch
    with pytest.raises(AuthPolicyError, match="main|whitespace"):
        validate_auth_receipt(tampered)

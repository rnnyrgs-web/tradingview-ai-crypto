import json

import pytest

from agents.claude_code_auth import (
    API_METERED,
    MANUAL_ADAPTER_REQUIRED,
    SUBSCRIPTION,
    AuthPolicyError,
    make_auth_receipt,
    resolve_auth,
    resolve_auth_from_environment,
    validate_auth_receipt,
)


MAIN = "a" * 40


def test_subscription_oauth_is_preferred_and_not_api_budgeted():
    decision = resolve_auth(oauth_present=True, api_key_present=True)
    assert decision.auth_mode == SUBSCRIPTION
    assert decision.execute is True
    assert decision.credential_ref == "CLAUDE_CODE_OAUTH_TOKEN"
    assert decision.budget_gate_required is False


def test_api_fallback_stays_explicitly_metered():
    decision = resolve_auth(oauth_present=False, api_key_present=True)
    assert decision.auth_mode == API_METERED
    assert decision.execute is True
    assert decision.credential_ref == "ANTHROPIC_API_KEY"
    assert decision.budget_gate_required is True


def test_missing_subscription_with_fallback_disabled_fails_closed():
    decision = resolve_auth(oauth_present=False, api_key_present=True, allow_api_fallback=False)
    assert decision.auth_mode == MANUAL_ADAPTER_REQUIRED
    assert decision.execute is False
    assert decision.credential_ref is None


def test_no_credentials_is_manual_adapter_required_not_silent_api():
    decision = resolve_auth(oauth_present=False, api_key_present=False)
    assert decision.auth_mode == MANUAL_ADAPTER_REQUIRED
    assert decision.execute is False
    assert decision.reason == "NO_SUPPORTED_CREDENTIAL_CONFIGURED"


def test_environment_values_are_never_serialized():
    oauth = "oauth-super-secret-value"
    api = "api-super-secret-value"
    decision = resolve_auth_from_environment(
        {"CLAUDE_CODE_OAUTH_TOKEN": oauth, "ANTHROPIC_API_KEY": api}
    )
    payload = json.dumps(decision.as_dict(), sort_keys=True)
    assert oauth not in payload
    assert api not in payload
    assert "CLAUDE_CODE_OAUTH_TOKEN" in payload


def test_auth_receipt_is_deterministic_secret_free_and_immutable(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "never-persist-this-token")
    decision = resolve_auth(oauth_present=True, api_key_present=False)
    kwargs = dict(
        task_id="V2-004-PROBE",
        request_id="run-123-attempt-1",
        branch="auto/testing-security/v2-004-probe",
        base_main_sha=MAIN,
        decision=decision,
        observed_at="2026-09-21T07:45:00Z",
    )
    first = make_auth_receipt(**kwargs)
    second = make_auth_receipt(**kwargs)
    assert first == second
    assert first["attempt_id"] == second["attempt_id"]
    assert first["auth_mode"] == SUBSCRIPTION
    assert first["budget_gate_required"] is False
    assert "never-persist-this-token" not in json.dumps(first)
    validate_auth_receipt(first)

    tampered = dict(first)
    tampered["auth_mode"] = API_METERED
    with pytest.raises(AuthPolicyError):
        validate_auth_receipt(tampered)


@pytest.mark.parametrize("branch", ["main", "master"])
def test_receipt_refuses_direct_main_write_identity(branch):
    decision = resolve_auth(oauth_present=True, api_key_present=False)
    with pytest.raises(AuthPolicyError, match="main"):
        make_auth_receipt(
            task_id="V2-004-PROBE",
            request_id="run-1",
            branch=branch,
            base_main_sha=MAIN,
            decision=decision,
            observed_at="2026-09-21T07:45:00Z",
        )


def test_provider_or_engine_mismatch_fails_closed():
    decision = resolve_auth(oauth_present=True, api_key_present=False)
    receipt = make_auth_receipt(
        task_id="V2-004-PROBE",
        request_id="run-1",
        branch="auto/testing-security/v2-004-probe",
        base_main_sha=MAIN,
        decision=decision,
        observed_at="2026-09-21T07:45:00Z",
    )
    bad = dict(receipt)
    bad["provider"] = "other-provider"
    with pytest.raises(AuthPolicyError, match="provider/engine"):
        validate_auth_receipt(bad)


def test_new_request_gets_new_attempt_identity():
    decision = resolve_auth(oauth_present=True, api_key_present=False)
    common = dict(
        task_id="V2-004-PROBE",
        branch="auto/testing-security/v2-004-probe",
        base_main_sha=MAIN,
        decision=decision,
        observed_at="2026-09-21T07:45:00Z",
    )
    a = make_auth_receipt(request_id="run-1", **common)
    b = make_auth_receipt(request_id="run-2", **common)
    assert a["attempt_id"] != b["attempt_id"]

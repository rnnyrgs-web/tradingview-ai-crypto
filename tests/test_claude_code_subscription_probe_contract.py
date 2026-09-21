from pathlib import Path


PROBE = Path(".github/workflows/claude_code_subscription_probe.yml")


def _text() -> str:
    return PROBE.read_text(encoding="utf-8")


def test_probe_is_read_only_and_does_not_expose_paid_api_fallback():
    text = _text()
    assert "permissions:\n  contents: read\n" in text
    assert "contents: write" not in text
    assert "issues: write" not in text
    assert "pull-requests: write" not in text
    assert "id-token: write" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: "1"' in text
    assert '--disallowedTools "Edit,Write,Replace,NotebookEditCell,Bash,WebSearch,WebFetch"' in text


def test_probe_pins_third_party_actions_to_exact_commits():
    text = _text()
    assert "anthropics/claude-code-action@cfc3eb22bfed5c26ef66e3223c982af27e4524de" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "anthropics/claude-code-action@v1" not in text
    assert "actions/upload-artifact@v4" not in text


def test_probe_is_trusted_main_manual_only_and_never_runs_on_pull_request_code():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "github.event.pull_request" not in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "TARGET_HEAD_SHA: ${{ github.sha }}" in text
    assert '"head_sha": target_head' in text
    assert '"execution_sha": os.environ["GITHUB_SHA"]' in text
    assert '"event_name": os.environ["GITHUB_EVENT_NAME"]' in text
    assert '"proof_ref": proof_ref' in text


def test_subscription_success_requires_model_structured_output_not_only_action_exit_zero():
    text = _text()
    assert "--json-schema" in text
    assert '"subscription_probe_ok"' in text
    assert 'PROBE_CONCLUSION: ${{ steps.oauth_probe.outputs.conclusion }}' in text
    assert 'PROBE_STRUCTURED_OUTPUT: ${{ steps.oauth_probe.outputs.structured_output }}' in text
    assert 'structured_ok = structured == {"subscription_probe_ok": True}' in text
    assert 'authenticated = configured and outcome == "success" and conclusion == "success" and structured_ok' in text
    assert '"structured_probe_verified": structured_ok' in text


def test_missing_or_failed_oauth_never_becomes_subscription_automated():
    text = _text()
    assert "if authenticated:" in text
    assert 'status = "SUBSCRIPTION_AUTOMATED"' in text
    assert "elif not configured:" in text
    assert 'status = "MANUAL_ADAPTER_REQUIRED"' in text
    assert 'status = "UNKNOWN"' in text
    assert "steps.preflight.outputs.configured == 'true'" in text
    assert "steps.oauth_probe.outcome != 'success'" in text
    assert "steps.oauth_probe.outputs.conclusion != 'success'" in text
    assert "subscription_probe_ok != true" in text

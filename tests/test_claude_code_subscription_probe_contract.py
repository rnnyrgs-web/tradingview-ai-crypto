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
    assert "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: \"1\"" in text
    assert "--disallowedTools \"Edit,Write,Replace,NotebookEditCell,Bash,WebSearch,WebFetch\"" in text


def test_probe_pins_third_party_actions_to_exact_commits():
    text = _text()
    assert "anthropics/claude-code-action@cfc3eb22bfed5c26ef66e3223c982af27e4524de" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "anthropics/claude-code-action@v1" not in text
    assert "actions/upload-artifact@v4" not in text


def test_probe_receipt_binds_pull_request_run_to_exact_pr_head_not_merge_ref():
    text = _text()
    assert (
        "TARGET_HEAD_SHA: ${{ github.event_name == 'pull_request' && "
        "github.event.pull_request.head.sha || github.sha }}"
    ) in text
    assert '"head_sha": target_head' in text
    assert '"execution_sha": os.environ["GITHUB_SHA"]' in text
    assert '"event_name": os.environ["GITHUB_EVENT_NAME"]' in text
    assert '"proof_ref": proof_ref' in text


def test_missing_or_failed_oauth_never_becomes_subscription_automated():
    text = _text()
    assert 'if configured and outcome == "success":' in text
    assert 'status = "SUBSCRIPTION_AUTOMATED"' in text
    assert 'elif not configured:' in text
    assert 'status = "MANUAL_ADAPTER_REQUIRED"' in text
    assert 'status = "UNKNOWN"' in text
    assert "steps.preflight.outputs.configured == 'true' && steps.oauth_probe.outcome != 'success'" in text

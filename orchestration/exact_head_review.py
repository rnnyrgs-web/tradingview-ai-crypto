from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # nosec B404 - fixed git argv used only to bind reviewer-runtime provenance
from pathlib import Path
from typing import Any

import httpx

from agents.autonomous_orchestrator import (
    REVIEWERS,
    _review_diff_claude_adversarial,
    diff_changed_paths,
    extract_json,
    model_name,
    post_response,
    response_text,
)
from orchestration.protected_paths import find_protected_matches
from orchestration.review_scope_policy import (
    REVIEW_RECEIPT_SCHEMA_VERSION,
    REVIEW_SCOPE_DISCIPLINE,
    REVIEW_SCOPE_POLICY_VERSION,
    changed_paths_sha256,
    classify_diff_scope,
    protected_path_registry_identity,
    review_receipt_context_sha256,
    review_scope_policy_sha256,
    verify_review_scope_receipt,
)
from orchestration.reviewer_trust_root import (
    collect_trusted_workflow_context,
    reviewer_trust_root_identity,
    seal_review_receipt_trust,
    verify_trust_bound_review_receipt,
)

MAX_DIFF_BYTES = 256_000
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RETRYABLE_PROVIDER_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})
REVIEW_SCOPE_DISCIPLINE_VERSION = REVIEW_SCOPE_POLICY_VERSION


def _review_scope_policy_sha256() -> str:
    return review_scope_policy_sha256()


def _validate_exact_head(pr_number: int, head_sha: str) -> None:
    if pr_number <= 0:
        raise RuntimeError("pr_number must be positive")
    if not _SHA_RE.fullmatch(head_sha):
        raise RuntimeError("head_sha must be an exact 40-character lowercase git SHA")


def _protected_context(diff: str) -> list[str]:
    return sorted(find_protected_matches(diff_changed_paths(diff)))


def _runtime_git_sha() -> str:
    try:
        value = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to determine reviewer-runtime git SHA") from exc
    if not _SHA_RE.fullmatch(value):
        raise RuntimeError("invalid reviewer-runtime git SHA")
    return value


def _workflow_provenance_from_env(runtime_git_sha: str | None = None) -> dict[str, Any]:
    """Return the legacy receipt subset of trusted workflow identity.

    Production review additionally requires collect_trusted_workflow_context(), which
    reconciles these values against server-observed GitHub Actions/main metadata.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id_raw = os.environ.get("GITHUB_RUN_ID", "")
    workflow_ref = os.environ.get("GITHUB_WORKFLOW_REF", "")
    if not repository or not run_id_raw or not workflow_ref:
        raise RuntimeError("trusted GitHub workflow provenance required")
    try:
        run_id = int(run_id_raw)
    except ValueError as exc:
        raise RuntimeError("invalid GitHub workflow run id") from exc
    if run_id <= 0:
        raise RuntimeError("invalid GitHub workflow run id")
    runtime_sha = runtime_git_sha if runtime_git_sha is not None else _runtime_git_sha()
    if not isinstance(runtime_sha, str) or not _SHA_RE.fullmatch(runtime_sha):
        raise RuntimeError("invalid reviewer-runtime git SHA")
    return {
        "repository": repository,
        "run_id": run_id,
        "workflow_ref": workflow_ref,
        "runtime_git_sha": runtime_sha,
    }


def _trusted_workflow_context_from_env(runtime_git_sha: str | None = None) -> dict[str, Any]:
    runtime_sha = runtime_git_sha if runtime_git_sha is not None else _runtime_git_sha()
    return collect_trusted_workflow_context(runtime_git_sha=runtime_sha)


def _legacy_provenance_from_trusted_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository": context["repository"],
        "run_id": context["run_id"],
        "workflow_ref": context["workflow_ref"],
        "runtime_git_sha": context["runtime_git_sha"],
    }


def _context_header(
    *,
    pr_number: int,
    head_sha: str,
    protected_hits: list[str],
    diff_scope: str,
    workflow_provenance: dict[str, Any],
    workflow_trust_context: dict[str, Any],
) -> str:
    protected = ", ".join(protected_hits) if protected_hits else "NONE"
    registry = protected_path_registry_identity()
    trust_root = reviewer_trust_root_identity()
    return (
        "READ_ONLY_EXACT_HEAD_REVIEW_CONTEXT\n"
        f"PR_NUMBER: {pr_number}\n"
        f"EXACT_HEAD_SHA: {head_sha}\n"
        f"DIFF_SCOPE_CLASS: {diff_scope}\n"
        f"PROTECTED_PATH_CONTEXT: {protected}\n"
        f"PROTECTED_PATH_REGISTRY_VERSION: {registry['version']}\n"
        f"PROTECTED_PATH_REGISTRY_SHA256: {registry['sha256']}\n"
        f"REVIEWER_TRUST_ROOT_SHA256: {trust_root['sha256']}\n"
        f"WORKFLOW_REPOSITORY: {workflow_provenance['repository']}\n"
        f"WORKFLOW_RUN_ID: {workflow_provenance['run_id']}\n"
        f"WORKFLOW_RUN_ATTEMPT: {workflow_trust_context['run_attempt']}\n"
        f"WORKFLOW_EVENT: {workflow_trust_context['event_name']}\n"
        f"WORKFLOW_REF: {workflow_provenance['workflow_ref']}\n"
        f"WORKFLOW_SHA: {workflow_trust_context['workflow_sha']}\n"
        f"WORKFLOW_RUNTIME_GIT_SHA: {workflow_provenance['runtime_git_sha']}\n"
        f"SERVER_RUN_HEAD_SHA: {workflow_trust_context['server_run_head_sha']}\n"
        f"SERVER_MAIN_SHA: {workflow_trust_context['server_main_sha']}\n"
        "INTEGRATION_AUTHORITY: NONE\n"
        f"REVIEW_SCOPE_POLICY_VERSION: {REVIEW_SCOPE_DISCIPLINE_VERSION}\n"
        f"REVIEW_SCOPE_POLICY_SHA256: {_review_scope_policy_sha256()}\n"
        f"{REVIEW_SCOPE_DISCIPLINE}\n"
        "IMPORTANT: Protected paths must receive full adversarial review. Their presence must never "
        "grant autonomous merge/integration authority; approval of a protected diff means only that "
        "the exact head may proceed to the separate Lead-only integration gate.\n"
    )


def _validate_verdict_schema(verdict: dict[str, Any]) -> None:
    if not isinstance(verdict.get("approve"), bool):
        raise RuntimeError("reviewer returned invalid approval")
    if verdict.get("risk") not in {"low", "medium", "high"}:
        raise RuntimeError("reviewer returned invalid risk")
    reason = verdict.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("reviewer returned invalid reason")


def _enrich_verdict(
    verdict: dict[str, Any],
    *,
    pr_number: int,
    head_sha: str,
    protected_hits: list[str],
    changed_paths: list[str],
    diff_scope: str,
    workflow_provenance: dict[str, Any],
    workflow_trust_context: dict[str, Any],
) -> dict[str, Any]:
    _validate_verdict_schema(verdict)
    canonical_paths = sorted(set(changed_paths))
    registry = protected_path_registry_identity()
    trust_root = reviewer_trust_root_identity()
    enriched = dict(verdict)
    enriched.update(
        {
            "review_receipt_schema_version": REVIEW_RECEIPT_SCHEMA_VERSION,
            "review_scope": "READ_ONLY_EXACT_HEAD",
            "review_scope_policy_version": REVIEW_SCOPE_DISCIPLINE_VERSION,
            "review_scope_policy_sha256": _review_scope_policy_sha256(),
            "changed_paths": canonical_paths,
            "changed_paths_sha256": changed_paths_sha256(canonical_paths),
            "diff_scope_class": diff_scope,
            "pr_number": pr_number,
            "exact_head_sha": head_sha,
            "protected_paths": protected_hits,
            "protected_path_registry": registry,
            "reviewer_trust_root": trust_root,
            "workflow_provenance": dict(workflow_provenance),
            "integration_authority": "NONE",
        }
    )
    enriched["review_context_sha256"] = review_receipt_context_sha256(
        pr_number=pr_number,
        exact_head_sha=head_sha,
        changed_paths=canonical_paths,
        diff_scope_class=diff_scope,
        workflow_repository=workflow_provenance["repository"],
        workflow_run_id=workflow_provenance["run_id"],
        workflow_ref=workflow_provenance["workflow_ref"],
        workflow_runtime_sha=workflow_provenance["runtime_git_sha"],
    )
    verify_review_scope_receipt(
        enriched,
        expected_pr_number=pr_number,
        expected_head_sha=head_sha,
        expected_changed_paths=canonical_paths,
        expected_diff_scope=diff_scope,
        expected_workflow_repository=workflow_provenance["repository"],
        expected_workflow_run_id=workflow_provenance["run_id"],
        expected_workflow_ref=workflow_provenance["workflow_ref"],
        expected_workflow_runtime_sha=workflow_provenance["runtime_git_sha"],
    )
    sealed = seal_review_receipt_trust(enriched, trusted_context=workflow_trust_context)
    verify_trust_bound_review_receipt(
        sealed,
        trusted_context=workflow_trust_context,
        current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
        require_approval=False,
    )
    return sealed


def _retryable_provider_transport(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_PROVIDER_STATUSES
    return False


def _claude_exact_head_verdict(review_input: str, temporary: Path) -> dict[str, Any]:
    """Run Claude once; classify malformed/transient output as a bounded non-verdict."""
    temporary.unlink(missing_ok=True)
    try:
        _review_diff_claude_adversarial(review_input, temporary)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
        if not _retryable_provider_transport(exc):
            raise
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer provider transport exhausted bounded retries"
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer returned malformed or incomplete JSON"
        ) from exc

    try:
        verdict = json.loads(temporary.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer returned malformed or incomplete JSON"
        ) from exc
    if not isinstance(verdict, dict):
        raise RuntimeError("reviewer returned non-object JSON")
    _validate_verdict_schema(verdict)
    return verdict


def _openai_exact_head_verdict(prompt: str) -> dict[str, Any]:
    """Run one OpenAI reviewer invocation and preserve hard-vs-transient failures."""
    try:
        response = post_response({"model": model_name(), "input": prompt})
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
        if not _retryable_provider_transport(exc):
            raise
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer provider transport exhausted bounded retries"
        ) from exc

    try:
        text = response_text(response)
    except (json.JSONDecodeError, TypeError, KeyError, AttributeError) as exc:
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer returned malformed or incomplete JSON"
        ) from exc
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("temporarily unavailable: OpenAI reviewer returned empty output")

    try:
        verdict = extract_json(text)
    except (json.JSONDecodeError, RuntimeError) as exc:
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer returned malformed or incomplete JSON"
        ) from exc
    _validate_verdict_schema(verdict)
    return verdict


def _trusted_context_for_review() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_sha = _runtime_git_sha()
    trusted_context = _trusted_workflow_context_from_env(runtime_sha)
    legacy_provenance = _legacy_provenance_from_trusted_context(trusted_context)
    return legacy_provenance, trusted_context


def review_exact_head(
    reviewer: str,
    diff_path: Path,
    output: Path,
    *,
    pr_number: int,
    head_sha: str,
) -> int:
    """Review one exact PR head under independently reconciled GitHub provenance."""
    if reviewer not in REVIEWERS:
        raise RuntimeError("unknown reviewer")
    _validate_exact_head(pr_number, head_sha)
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
        raise RuntimeError("diff too large")
    if not diff.strip():
        raise RuntimeError("diff is empty")

    # Trust-root/server reconciliation happens before diff policy or any paid model
    # invocation. Registry/policy drift likewise fails while constructing the header.
    workflow_provenance, workflow_trust_context = _trusted_context_for_review()
    changed_paths = diff_changed_paths(diff)
    diff_scope = classify_diff_scope(changed_paths)
    protected_hits = _protected_context(diff)
    header = _context_header(
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
        diff_scope=diff_scope,
        workflow_provenance=workflow_provenance,
        workflow_trust_context=workflow_trust_context,
    )
    review_input = f"{header}\nPROPOSED DIFF:\n{diff}"

    if reviewer == "claude-adversarial":
        temporary = output.with_suffix(output.suffix + ".raw")
        try:
            verdict = _claude_exact_head_verdict(review_input, temporary)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        focus = (
            "security, secret handling, path boundaries, malformed input, fail-closed behavior, and whether tests can be bypassed"
            if reviewer == "security"
            else "correctness, compatibility, no-lookahead, research/live isolation, scientific-gate integrity, regression risk, and scope discipline"
        )
        prompt = f"""
You are the independent {reviewer} reviewer for an autonomous crypto trading software change.
Review focus: {focus}.

{review_input}

Return JSON only:
{{"approve": true|false, "reason": "specific evidence-based reason", "risk": "low|medium|high"}}
Approve only if the exact diff is bounded, internally coherent, does not weaken safety/scientific gates,
and has no unsupported live-trading or promotion claim. Protected scientific paths are NOT a reason to
skip review: scrutinize them more heavily. Approval never grants merge/integration authority. When
evidence is insufficient for a claim or authority the diff actually grants, reject; apply the explicit
review-scope discipline above. REVIEW_INFRASTRUCTURE means audit the meta-control itself.
PROTECTED_SCIENTIFIC_GATE_MUTATION means audit every changed protected gate/control now and do not defer
its changed semantics as future evidence; genuinely unopened future outcomes may remain sealed only when
the exact executable closure and later gate are present and fail closed. GENERAL_RESEARCH_OR_CODE has no
protected-path mutation. The discipline never excuses missing executable closure controls or gates.
"""
        verdict = _openai_exact_head_verdict(prompt)

    enriched = _enrich_verdict(
        verdict,
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
        changed_paths=changed_paths,
        diff_scope=diff_scope,
        workflow_provenance=workflow_provenance,
        workflow_trust_context=workflow_trust_context,
    )
    output.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _verify_current_receipt(
    *,
    receipt_path: Path,
    diff_path: Path,
    pr_number: int,
    head_sha: str,
    require_approval: bool,
) -> None:
    _validate_exact_head(pr_number, head_sha)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("review receipt must be one JSON object")
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
        raise RuntimeError("diff too large")
    if not diff.strip():
        raise RuntimeError("diff is empty")

    workflow_provenance, workflow_trust_context = _trusted_context_for_review()
    changed_paths = diff_changed_paths(diff)
    diff_scope = classify_diff_scope(changed_paths)
    verify_review_scope_receipt(
        payload,
        expected_pr_number=pr_number,
        expected_head_sha=head_sha,
        expected_changed_paths=changed_paths,
        expected_diff_scope=diff_scope,
        expected_workflow_repository=workflow_provenance["repository"],
        expected_workflow_run_id=workflow_provenance["run_id"],
        expected_workflow_ref=workflow_provenance["workflow_ref"],
        expected_workflow_runtime_sha=workflow_provenance["runtime_git_sha"],
    )
    verify_trust_bound_review_receipt(
        payload,
        trusted_context=workflow_trust_context,
        current_schema_version=REVIEW_RECEIPT_SCHEMA_VERSION,
        require_approval=require_approval,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review")
    review.add_argument("--reviewer", choices=sorted(REVIEWERS), required=True)
    review.add_argument("--diff", required=True)
    review.add_argument("--output", required=True)
    review.add_argument("--pr-number", type=int, required=True)
    review.add_argument("--head-sha", required=True)

    for command in ("verify-current-receipt", "verify-current-approval"):
        verify = sub.add_parser(command)
        verify.add_argument("--receipt", required=True)
        verify.add_argument("--diff", required=True)
        verify.add_argument("--pr-number", type=int, required=True)
        verify.add_argument("--head-sha", required=True)

    args = parser.parse_args()
    if args.command == "review":
        return review_exact_head(
            args.reviewer,
            Path(args.diff),
            Path(args.output),
            pr_number=args.pr_number,
            head_sha=args.head_sha,
        )
    if args.command in {"verify-current-receipt", "verify-current-approval"}:
        _verify_current_receipt(
            receipt_path=Path(args.receipt),
            diff_path=Path(args.diff),
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            require_approval=args.command == "verify-current-approval",
        )
        return 0
    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

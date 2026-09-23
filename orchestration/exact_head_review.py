from __future__ import annotations

import argparse
import json
import re
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
    review_receipt_context_sha256,
    review_scope_policy_sha256,
    verify_review_scope_receipt,
)

# Protected scientific repairs such as #507 legitimately span schema, durable
# rejected-memory and regression files. Keep a hard context bound, but size it
# for one coherent full exact-head review rather than silently forcing a partial
# review of a >80 kB scientific gate change.
MAX_DIFF_BYTES = 256_000
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RETRYABLE_PROVIDER_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})

# Compatibility aliases retained for focused tests and older callers.
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


def _context_header(
    *,
    pr_number: int,
    head_sha: str,
    protected_hits: list[str],
    diff_scope: str,
) -> str:
    protected = ", ".join(protected_hits) if protected_hits else "NONE"
    return (
        "READ_ONLY_EXACT_HEAD_REVIEW_CONTEXT\n"
        f"PR_NUMBER: {pr_number}\n"
        f"EXACT_HEAD_SHA: {head_sha}\n"
        f"DIFF_SCOPE_CLASS: {diff_scope}\n"
        f"PROTECTED_PATH_CONTEXT: {protected}\n"
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
) -> dict[str, Any]:
    _validate_verdict_schema(verdict)
    canonical_paths = sorted(set(changed_paths))
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
            "integration_authority": "NONE",
        }
    )
    enriched["review_context_sha256"] = review_receipt_context_sha256(
        pr_number=pr_number,
        exact_head_sha=head_sha,
        changed_paths=canonical_paths,
        diff_scope_class=diff_scope,
    )
    verify_review_scope_receipt(
        enriched,
        expected_pr_number=pr_number,
        expected_head_sha=head_sha,
        expected_changed_paths=canonical_paths,
        expected_diff_scope=diff_scope,
    )
    return enriched


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


def review_exact_head(
    reviewer: str,
    diff_path: Path,
    output: Path,
    *,
    pr_number: int,
    head_sha: str,
) -> int:
    """Review one exact PR head without treating protected files as unreviewable.

    This command is deliberately review-only. Protected-path detection becomes reviewer
    context and a durable receipt field; it never becomes autonomous integration authority.
    The surrounding workflow has contents:read only and records protected approvals as
    Lead-integration-required.
    """

    if reviewer not in REVIEWERS:
        raise RuntimeError("unknown reviewer")
    _validate_exact_head(pr_number, head_sha)
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
        raise RuntimeError("diff too large")
    if not diff.strip():
        raise RuntimeError("diff is empty")

    changed_paths = diff_changed_paths(diff)
    diff_scope = classify_diff_scope(changed_paths)
    protected_hits = _protected_context(diff)
    header = _context_header(
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
        diff_scope=diff_scope,
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
review-scope discipline above. DIFF_SCOPE_CLASS is executable: REVIEW_INFRASTRUCTURE means market-strategy
evidence is not a claim of this meta-control diff, so audit the control itself; GENERAL_RESEARCH_OR_CODE keeps
the fail-closed future-evidence rule. The discipline never excuses missing executable closure controls or gates.
"""
        verdict = _openai_exact_head_verdict(prompt)

    enriched = _enrich_verdict(
        verdict,
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
        changed_paths=changed_paths,
        diff_scope=diff_scope,
    )
    output.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review")
    review.add_argument("--reviewer", choices=sorted(REVIEWERS), required=True)
    review.add_argument("--diff", required=True)
    review.add_argument("--output", required=True)
    review.add_argument("--pr-number", type=int, required=True)
    review.add_argument("--head-sha", required=True)

    verify = sub.add_parser("verify-receipt")
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
    if args.command == "verify-receipt":
        _validate_exact_head(args.pr_number, args.head_sha)
        payload = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("review receipt must be one JSON object")
        diff = Path(args.diff).read_text(encoding="utf-8")
        if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
            raise RuntimeError("diff too large")
        if not diff.strip():
            raise RuntimeError("diff is empty")
        changed_paths = diff_changed_paths(diff)
        diff_scope = classify_diff_scope(changed_paths)
        verify_review_scope_receipt(
            payload,
            expected_pr_number=args.pr_number,
            expected_head_sha=args.head_sha,
            expected_changed_paths=changed_paths,
            expected_diff_scope=diff_scope,
        )
        return 0
    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

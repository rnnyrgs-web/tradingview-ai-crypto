from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

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

# Protected scientific repairs such as #507 legitimately span schema, durable
# rejected-memory and regression files. Keep a hard context bound, but size it
# for one coherent full exact-head review rather than silently forcing a partial
# review of a >80 kB scientific gate change.
MAX_DIFF_BYTES = 256_000
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RETRYABLE_PROVIDER_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})


def _validate_exact_head(pr_number: int, head_sha: str) -> None:
    if pr_number <= 0:
        raise RuntimeError("pr_number must be positive")
    if not _SHA_RE.fullmatch(head_sha):
        raise RuntimeError("head_sha must be an exact 40-character lowercase git SHA")


def _protected_context(diff: str) -> list[str]:
    return sorted(find_protected_matches(diff_changed_paths(diff)))


def _context_header(*, pr_number: int, head_sha: str, protected_hits: list[str]) -> str:
    protected = ", ".join(protected_hits) if protected_hits else "NONE"
    return (
        "READ_ONLY_EXACT_HEAD_REVIEW_CONTEXT\n"
        f"PR_NUMBER: {pr_number}\n"
        f"EXACT_HEAD_SHA: {head_sha}\n"
        f"PROTECTED_PATH_CONTEXT: {protected}\n"
        "INTEGRATION_AUTHORITY: NONE\n"
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
) -> dict[str, Any]:
    _validate_verdict_schema(verdict)
    enriched = dict(verdict)
    enriched.update(
        {
            "review_scope": "READ_ONLY_EXACT_HEAD",
            "pr_number": pr_number,
            "exact_head_sha": head_sha,
            "protected_paths": protected_hits,
            "integration_authority": "NONE",
        }
    )
    return enriched


def _valid_attempt_verdicts(verdicts: Iterable[dict[str, Any] | None]) -> list[dict[str, Any]]:
    valid_verdicts: list[dict[str, Any]] = []
    for verdict in verdicts:
        if verdict is None:
            continue
        try:
            _validate_verdict_schema(verdict)
        except RuntimeError:
            continue
        if verdict.get("integration_authority") != "NONE":
            continue
        valid_verdicts.append(verdict)
    return valid_verdicts


def load_attempt_verdicts(paths: Iterable[Path]) -> list[dict[str, Any] | None]:
    """Load reviewer files once under one canonical fail-closed interpretation.

    Live rejection detection and durable attempt finalization both use this exact
    loader so malformed/missing files cannot be filtered differently by two shell
    snippets. A non-object or invalid/integration-authority-bearing document is a
    non-verdict, never an approval and never a scientific rejection.
    """

    verdicts: list[dict[str, Any] | None] = []
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            verdicts.append(None)
            continue
        if not isinstance(value, dict):
            verdicts.append(None)
            continue
        try:
            _validate_verdict_schema(value)
        except RuntimeError:
            verdicts.append(None)
            continue
        if value.get("integration_authority") != "NONE":
            verdicts.append(None)
            continue
        verdicts.append(value)
    return verdicts


def has_terminal_rejection(verdicts: Iterable[dict[str, Any] | None]) -> bool:
    """Return one deterministic rejection predicate shared by live and receipt paths."""

    return any(verdict["approve"] is False for verdict in _valid_attempt_verdicts(verdicts))


def has_terminal_rejection_files(paths: Iterable[Path]) -> bool:
    """Canonical file-backed terminal-rejection predicate used by the live workflow."""

    return has_terminal_rejection(load_attempt_verdicts(paths))


def classify_review_attempt_outcome(
    verdicts: Iterable[dict[str, Any] | None],
    *,
    controlled_wait: bool,
    approved_outcome: str,
) -> str:
    """Classify one multi-reviewer attempt without ever retrying past a valid rejection.

    A valid scientific rejection is terminal for the exact candidate SHA even if a
    different provider was transient or unavailable in the same attempt. WAIT is
    reserved for attempts that contain no valid rejection and are missing required
    reviewer evidence only because of bounded transient capacity/runtime failure.
    """

    verdict_list = list(verdicts)
    valid_verdicts = _valid_attempt_verdicts(verdict_list)
    if has_terminal_rejection(verdict_list):
        return "REJECTED"
    if controlled_wait:
        return "WAIT_RETRYABLE"
    if approved_outcome.startswith("REVIEW_APPROVED_"):
        if len(valid_verdicts) == 3 and all(verdict["approve"] is True for verdict in valid_verdicts):
            return approved_outcome
        return "FAILED"
    return "FAILED"


def classify_review_attempt_files(
    paths: Iterable[Path],
    *,
    controlled_wait: bool,
    approved_outcome: str,
) -> str:
    """Canonical file-backed attempt classifier used by durable finalization."""

    return classify_review_attempt_outcome(
        load_attempt_verdicts(paths),
        controlled_wait=controlled_wait,
        approved_outcome=approved_outcome,
    )


def _retryable_provider_transport(exc: BaseException) -> bool:
    """Recognize only provider failures that the lower HTTP client already retries.

    Exact-head review must not turn a final exhausted timeout/5xx into a scientific
    failure merely because the shell log does not contain one narrow rate-limit phrase.
    Conversely, authentication/configuration/client errors such as 400/401/403 remain
    hard failures and must never be silently converted into retryable WAIT state.
    """

    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_PROVIDER_STATUSES
    return False


def _claude_exact_head_verdict(review_input: str, temporary: Path) -> dict[str, Any]:
    """Preserve the existing Claude scientific invocation exactly; reclassify non-verdicts only.

    The same ``review_input`` is passed directly to the same adversarial reviewer function
    exactly once. Valid approvals and valid scientific rejections are returned unchanged.
    Missing/unreadable raw output, malformed/truncated JSON, invalid verdict schema, or an
    exhausted retryable provider transport failure is not a scientific verdict, so it becomes
    ``temporarily unavailable`` and the already-bounded *outer workflow* may retry the exact
    head later. Non-retryable HTTP/auth/configuration failures remain hard failures.
    """

    temporary.unlink(missing_ok=True)
    try:
        _review_diff_claude_adversarial(review_input, temporary)
        verdict = json.loads(temporary.read_text(encoding="utf-8"))
        if not isinstance(verdict, dict):
            raise RuntimeError("claude reviewer returned non-object JSON")
        _validate_verdict_schema(verdict)
        return verdict
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
        if not _retryable_provider_transport(exc):
            raise
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer provider transport exhausted bounded retries"
        ) from exc
    except (json.JSONDecodeError, RuntimeError, OSError) as exc:
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer returned missing, unreadable, malformed, incomplete, or invalid-schema JSON"
        ) from exc


def _openai_exact_head_verdict(prompt: str) -> dict[str, Any]:
    """Treat exhausted retryable transport/output failures as bounded non-verdicts.

    ``post_response`` already performs bounded retries for timeouts/network failures and
    HTTP 408/409/429/5xx responses. If those retries are exhausted, the reviewer produced no
    scientific verdict and the outer workflow should enter bounded WAIT. Non-retryable HTTP
    errors (for example 400/401/403), authentication/configuration failures, and other hard
    runtime faults remain hard failures. Valid approval/rejection output is unchanged and no
    second scientific invocation is introduced here.
    """

    model = model_name()
    try:
        response = post_response({"model": model, "input": prompt})
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
        if not _retryable_provider_transport(exc):
            raise
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer provider transport exhausted bounded retries"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer returned a malformed provider response"
        ) from exc

    try:
        text = response_text(response)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenAI reviewer returned empty output")
        verdict = extract_json(text)
        _validate_verdict_schema(verdict)
        return verdict
    except (json.JSONDecodeError, RuntimeError, TypeError, KeyError, AttributeError) as exc:
        raise RuntimeError(
            "temporarily unavailable: OpenAI reviewer returned missing, unreadable, malformed, incomplete, or invalid-schema JSON"
        ) from exc


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

    protected_hits = _protected_context(diff)
    header = _context_header(
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
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
evidence is insufficient, reject.
"""
        verdict = _openai_exact_head_verdict(prompt)

    enriched = _enrich_verdict(
        verdict,
        pr_number=pr_number,
        head_sha=head_sha,
        protected_hits=protected_hits,
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

    args = parser.parse_args()
    if args.command == "review":
        return review_exact_head(
            args.reviewer,
            Path(args.diff),
            Path(args.output),
            pr_number=args.pr_number,
            head_sha=args.head_sha,
        )
    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

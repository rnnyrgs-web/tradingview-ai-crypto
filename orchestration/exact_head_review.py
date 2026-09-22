from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

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


def _valid_attempt_verdicts(verdicts: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
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


def has_terminal_rejection(verdicts: list[dict[str, Any] | None]) -> bool:
    """Return one deterministic rejection predicate shared by live and receipt paths."""

    return any(verdict["approve"] is False for verdict in _valid_attempt_verdicts(verdicts))


def classify_review_attempt_outcome(
    verdicts: list[dict[str, Any] | None],
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

    valid_verdicts = _valid_attempt_verdicts(verdicts)
    if has_terminal_rejection(verdicts):
        return "REJECTED"
    if controlled_wait:
        return "WAIT_RETRYABLE"
    if approved_outcome.startswith("REVIEW_APPROVED_"):
        if len(valid_verdicts) == 3 and all(verdict["approve"] is True for verdict in valid_verdicts):
            return approved_outcome
        return "FAILED"
    return "FAILED"


def _claude_exact_head_verdict(review_input: str, temporary: Path) -> dict[str, Any]:
    """Preserve the existing Claude scientific invocation exactly; reclassify format failure only.

    The same ``review_input`` is passed directly to the same adversarial reviewer function
    exactly once. Valid approvals and valid scientific rejections are returned unchanged.
    Missing/unreadable raw output, malformed/truncated JSON, or an invalid verdict schema is
    not a scientific verdict, so it becomes ``temporarily unavailable`` and the already-bounded
    *outer workflow* may retry the exact head later. This helper never selects among multiple
    model judgments.
    """

    temporary.unlink(missing_ok=True)
    try:
        _review_diff_claude_adversarial(review_input, temporary)
        verdict = json.loads(temporary.read_text(encoding="utf-8"))
        if not isinstance(verdict, dict):
            raise RuntimeError("claude reviewer returned non-object JSON")
        _validate_verdict_schema(verdict)
        return verdict
    except (json.JSONDecodeError, RuntimeError, OSError) as exc:
        raise RuntimeError(
            "temporarily unavailable: Claude reviewer returned missing, unreadable, malformed, incomplete, or invalid-schema JSON"
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
        response = post_response({"model": model_name(), "input": prompt})
        verdict = extract_json(response_text(response))

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

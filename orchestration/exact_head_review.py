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
CLAUDE_FORMAT_ATTEMPTS = 2
CLAUDE_OUTPUT_BUDGET_GUIDANCE = (
    "REVIEW_OUTPUT_BUDGET: Return exactly one complete JSON object. "
    "Keep reason <= 60 words and each required falsification finding <= 24 words. "
    "Do not omit any required finding. Do not add markdown or prose outside the JSON."
)


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


def _claude_exact_head_verdict(review_input: str, temporary: Path) -> dict[str, Any]:
    """Run Claude with one bounded format-only retry.

    Scientific rejection is a normal valid JSON verdict and is never retried.
    The retry exists only for provider-format failures (truncated/malformed JSON or
    an invalid verdict schema). If both attempts fail formatting, raise a message
    the workflow already classifies as transient so the exact head remains
    unapproved and may use the existing bounded retry policy instead of being
    misclassified as a scientific failure.
    """

    last_error: Exception | None = None
    bounded_input = f"{review_input}\n\n{CLAUDE_OUTPUT_BUDGET_GUIDANCE}"
    for _attempt in range(CLAUDE_FORMAT_ATTEMPTS):
        temporary.unlink(missing_ok=True)
        try:
            _review_diff_claude_adversarial(bounded_input, temporary)
            verdict = json.loads(temporary.read_text(encoding="utf-8"))
            if not isinstance(verdict, dict):
                raise RuntimeError("claude reviewer returned non-object JSON")
            _validate_verdict_schema(verdict)
            return verdict
        except (json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc

    raise RuntimeError(
        "temporarily unavailable: Claude reviewer returned malformed or incomplete JSON "
        f"for {CLAUDE_FORMAT_ATTEMPTS} bounded attempts"
    ) from last_error


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

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

REVIEW_SCOPE_POLICY_VERSION = 4
REVIEW_RECEIPT_SCHEMA_VERSION = 3
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Fail closed: one changed strategy/research/runtime path is enough to leave the
# special review-infrastructure scope. Tests belong here only because they verify
# this exact meta-control and cannot grant runtime/research authority themselves.
REVIEW_INFRASTRUCTURE_PATHS = frozenset(
    {
        "orchestration/exact_head_review.py",
        "orchestration/review_scope_policy.py",
        "tests/test_exact_head_review.py",
        "tests/test_review_scope_policy.py",
    }
)

REVIEW_SCOPE_DISCIPLINE = (
    "REVIEW_SCOPE_DISCIPLINE: Judge this exact diff against the claims and authority it actually grants. "
    "DIFF_SCOPE_CLASS is produced by executable changed-path classification. For REVIEW_INFRASTRUCTURE, "
    "market-strategy evidence categories such as realized P&L, achieved sample size, baseline performance, "
    "regime results, protected OOS, costs, or forward evidence are not claims of that meta-control diff; audit "
    "the review control itself for correctness, bypasses, gate weakening, receipt integrity, and whether it could "
    "cause later scientific reviews to accept unsupported claims. Statistical multiple-testing obligations are not "
    "invented for review-policy wording unless policy variants were selected using empirical strategy outcomes. "
    "The infrastructure allowlist is part of the policy digest; changing path membership changes receipt identity "
    "and therefore cannot silently reuse prior review-policy receipts. Any path outside the strict infrastructure "
    "allowlist forces GENERAL_RESEARCH_OR_CODE. For a pre-outcome predeclaration/research-infrastructure diff "
    "classified GENERAL_RESEARCH_OR_CODE, an unavailable future-evidence category may be "
    "NOT_APPLICABLE_FOR_THIS_PHASE only when the exact diff/current main contains concrete machine-readable or "
    "executable controls that prevent current access/use of that evidence, predeclare the future gate before the "
    "evidence can be opened, and fail closed if the gate is absent or violated. Claims, comments, labels, or prose "
    "alone NEVER satisfy those conditions. missing, ambiguous, bypassable, post-hoc, or weakened controls require "
    "REJECT. This NEVER lowers the eventual evidence standard, never excuses an incomplete predeclaration, and "
    "never permits premature protected access or grants promotion, protected-OOS, broker, or trading authority. "
    "Review receipts are integrity records, not authentication or merge tokens: they must be revalidated against "
    "trusted PR/head/diff context before consumption, while GitHub workflow/issue provenance remains the authority "
    "for who produced the review. Historical prose may describe an earlier prerequisite; executable exact-head state "
    "is authoritative. Keep reviewer JSON concise: each falsification finding should be at most 24 words and the "
    "complete JSON should stay below 1400 tokens while still covering every material finding."
)

# Historical policy text must remain registered when a later version is added.
# A same-version edit changes the digest and therefore invalidates old receipts
# instead of silently reinterpreting them. The allowlist is also digest-bound.
REVIEW_SCOPE_POLICIES: dict[int, str] = {
    REVIEW_SCOPE_POLICY_VERSION: REVIEW_SCOPE_DISCIPLINE,
}


def review_scope_policy_sha256(version: int = REVIEW_SCOPE_POLICY_VERSION) -> str:
    discipline = REVIEW_SCOPE_POLICIES.get(version)
    if discipline is None:
        raise RuntimeError("unknown review-scope policy version")
    canonical = json.dumps(
        {
            "version": version,
            "discipline": discipline,
            "review_infrastructure_paths": sorted(REVIEW_INFRASTRUCTURE_PATHS),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_changed_paths(changed_paths: Iterable[str]) -> tuple[str, ...]:
    paths = tuple(sorted(set(changed_paths)))
    if not paths:
        raise RuntimeError("diff contains no changed paths")
    if any(not isinstance(path, str) or not path for path in paths):
        raise RuntimeError("invalid changed path")
    return paths


def changed_paths_sha256(changed_paths: Iterable[str]) -> str:
    paths = _canonical_changed_paths(changed_paths)
    canonical = json.dumps(paths, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_diff_scope(changed_paths: Iterable[str]) -> str:
    paths = _canonical_changed_paths(changed_paths)
    if all(path in REVIEW_INFRASTRUCTURE_PATHS for path in paths):
        return "REVIEW_INFRASTRUCTURE"
    return "GENERAL_RESEARCH_OR_CODE"


def review_receipt_context_sha256(
    *,
    pr_number: int,
    exact_head_sha: str,
    changed_paths: Iterable[str],
    diff_scope_class: str,
    policy_version: int = REVIEW_SCOPE_POLICY_VERSION,
) -> str:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise RuntimeError("invalid review PR number")
    if not isinstance(exact_head_sha, str) or not _SHA_RE.fullmatch(exact_head_sha):
        raise RuntimeError("invalid exact review head SHA")
    canonical_paths = _canonical_changed_paths(changed_paths)
    expected_scope = classify_diff_scope(canonical_paths)
    if diff_scope_class != expected_scope:
        raise RuntimeError("diff-scope classification mismatch")
    canonical = json.dumps(
        {
            "pr_number": pr_number,
            "exact_head_sha": exact_head_sha,
            "changed_paths": canonical_paths,
            "changed_paths_sha256": changed_paths_sha256(canonical_paths),
            "diff_scope_class": diff_scope_class,
            "review_scope_policy_version": policy_version,
            "review_scope_policy_sha256": review_scope_policy_sha256(policy_version),
            "integration_authority": "NONE",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_review_scope_receipt(
    receipt: dict[str, Any],
    *,
    expected_pr_number: int | None = None,
    expected_head_sha: str | None = None,
    expected_changed_paths: Iterable[str] | None = None,
    expected_diff_scope: str | None = None,
) -> None:
    # A receipt is never allowed to authenticate its own context. Callers must
    # supply PR/head/diff facts from the trusted workflow or equivalent source.
    if (
        expected_pr_number is None
        or expected_head_sha is None
        or expected_changed_paths is None
        or expected_diff_scope is None
    ):
        raise RuntimeError("trusted review context required")

    schema_version = receipt.get("review_receipt_schema_version")
    if isinstance(schema_version, bool) or schema_version != REVIEW_RECEIPT_SCHEMA_VERSION:
        raise RuntimeError("unsupported review receipt schema version")
    if receipt.get("review_scope") != "READ_ONLY_EXACT_HEAD":
        raise RuntimeError("invalid review scope")
    version = receipt.get("review_scope_policy_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise RuntimeError("invalid review-scope policy version")
    expected_policy_sha = review_scope_policy_sha256(version)
    if receipt.get("review_scope_policy_sha256") != expected_policy_sha:
        raise RuntimeError("review-scope policy digest mismatch")

    if isinstance(expected_pr_number, bool) or not isinstance(expected_pr_number, int) or expected_pr_number <= 0:
        raise RuntimeError("invalid trusted review PR number")
    if receipt.get("pr_number") != expected_pr_number:
        raise RuntimeError("review PR number mismatch")
    if not isinstance(expected_head_sha, str) or not _SHA_RE.fullmatch(expected_head_sha):
        raise RuntimeError("invalid trusted exact review head SHA")
    if receipt.get("exact_head_sha") != expected_head_sha:
        raise RuntimeError("exact review head SHA mismatch")

    trusted_paths = list(_canonical_changed_paths(expected_changed_paths))
    trusted_scope = classify_diff_scope(trusted_paths)
    if expected_diff_scope != trusted_scope:
        raise RuntimeError("trusted diff-scope classification mismatch")

    raw_paths = receipt.get("changed_paths")
    if not isinstance(raw_paths, list) or any(not isinstance(path, str) for path in raw_paths):
        raise RuntimeError("invalid changed paths")
    canonical_paths = list(_canonical_changed_paths(raw_paths))
    if raw_paths != canonical_paths:
        raise RuntimeError("changed paths must be canonical and unique")
    if canonical_paths != trusted_paths:
        raise RuntimeError("review changed paths do not match trusted diff")
    if receipt.get("changed_paths_sha256") != changed_paths_sha256(trusted_paths):
        raise RuntimeError("changed-path digest mismatch")
    if receipt.get("diff_scope_class") != trusted_scope or receipt.get("diff_scope_class") != expected_diff_scope:
        raise RuntimeError("diff-scope classification mismatch")
    if receipt.get("integration_authority") != "NONE":
        raise RuntimeError("review receipt must not grant integration authority")

    expected_context_sha = review_receipt_context_sha256(
        pr_number=expected_pr_number,
        exact_head_sha=expected_head_sha,
        changed_paths=trusted_paths,
        diff_scope_class=expected_diff_scope,
        policy_version=version,
    )
    if receipt.get("review_context_sha256") != expected_context_sha:
        raise RuntimeError("review trusted-context digest mismatch")

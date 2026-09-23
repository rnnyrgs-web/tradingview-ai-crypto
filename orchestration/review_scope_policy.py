from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from orchestration.protected_paths import find_protected_matches, load_protected_paths

REVIEW_SCOPE_POLICY_VERSION = 5
REVIEW_RECEIPT_SCHEMA_VERSION = 4
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

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
    "DIFF_SCOPE_CLASS is produced by executable changed-path classification against both the strict review-"
    "infrastructure allowlist and the canonical protected-path registry. REVIEW_INFRASTRUCTURE means only the "
    "review meta-control allowlist changed; audit it for correctness, bypasses, receipt/provenance integrity, and "
    "whether it could cause later scientific reviews to accept unsupported claims. PROTECTED_SCIENTIFIC_GATE_MUTATION "
    "means at least one canonical protected path changed outside that allowlist. In that class, the semantics of every "
    "changed protected gate/control must be audited NOW and may not be waved away as future evidence. This prevents a "
    "future gate-weakening diff from hiding behind phase deferral. Deliberately unopened realized P&L, achieved sample "
    "size, regime outcomes, protected OOS/forward results, realized overlap, or venue-calibrated realized costs may "
    "still be NOT_APPLICABLE_FOR_THIS_PHASE when concrete machine-readable or executable controls keep them closed, "
    "predeclare the later gate before access, and fail closed if the gate is absent or violated. GENERAL_RESEARCH_OR_CODE "
    "applies only when no protected path changes. Claims, comments, labels, or prose alone NEVER establish an evidence "
    "closure gate. Missing, ambiguous, bypassable, post-hoc, or weakened controls require REJECT. Do not require "
    "deliberately closed future P&L/OOS/forward evidence to be opened merely to approve the gate that keeps it closed. "
    "Unchanged executable code already integrated on canonical main is the trusted review baseline and need not be "
    "copied into every candidate diff; audit the changed code's exact binding to that baseline and reject if missing, "
    "ambiguous, stale, or weakened. The protected-path registry itself is digest-bound into this policy, so changes to "
    "what counts as protected cannot silently reuse old scope receipts. Production review receipts are integrity records, "
    "not authentication or merge tokens: they must bind trusted GitHub repository/workflow-run/workflow-ref provenance "
    "in addition to PR/head/diff/policy context, and consumers must supply that provenance independently. An offline JSON "
    "file cannot authenticate itself. Durable GitHub workflow/issue provenance remains the authority for who produced a "
    "review; no external legal or signed ledger is invented unless another frozen gate requires it. This NEVER lowers "
    "the eventual evidence standard, never excuses incomplete predeclaration, and never permits premature protected "
    "access or grants promotion, broker, protected-OOS, or trading authority. Historical prose may describe an earlier "
    "prerequisite; executable exact-head state is authoritative. Keep reviewer JSON concise while covering every material "
    "finding."
)

REVIEW_SCOPE_POLICIES: dict[int, str] = {
    REVIEW_SCOPE_POLICY_VERSION: REVIEW_SCOPE_DISCIPLINE,
}


def _canonical_changed_paths(changed_paths: Iterable[str]) -> tuple[str, ...]:
    raw_paths = tuple(changed_paths)
    if not raw_paths:
        raise RuntimeError("diff contains no changed paths")
    if any(not isinstance(path, str) or not path for path in raw_paths):
        raise RuntimeError("invalid changed path")
    return tuple(sorted(set(raw_paths)))


def _canonical_protected_paths(changed_paths: Iterable[str]) -> tuple[str, ...]:
    paths = _canonical_changed_paths(changed_paths)
    return tuple(find_protected_matches(list(paths)))


def _workflow_provenance(
    repository: str,
    run_id: int,
    workflow_ref: str,
) -> dict[str, Any]:
    if not isinstance(repository, str) or _REPO_RE.fullmatch(repository) is None:
        raise RuntimeError("invalid trusted workflow repository")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise RuntimeError("invalid trusted workflow run id")
    if not isinstance(workflow_ref, str) or not workflow_ref.strip() or len(workflow_ref) > 1024:
        raise RuntimeError("invalid trusted workflow ref")
    return {
        "repository": repository,
        "run_id": run_id,
        "workflow_ref": workflow_ref.strip(),
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
            "protected_path_patterns": list(load_protected_paths()),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def changed_paths_sha256(changed_paths: Iterable[str]) -> str:
    paths = _canonical_changed_paths(changed_paths)
    canonical = json.dumps(paths, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_diff_scope(changed_paths: Iterable[str]) -> str:
    paths = _canonical_changed_paths(changed_paths)
    if all(path in REVIEW_INFRASTRUCTURE_PATHS for path in paths):
        return "REVIEW_INFRASTRUCTURE"
    if _canonical_protected_paths(paths):
        return "PROTECTED_SCIENTIFIC_GATE_MUTATION"
    return "GENERAL_RESEARCH_OR_CODE"


def review_receipt_context_sha256(
    *,
    pr_number: int,
    exact_head_sha: str,
    changed_paths: Iterable[str],
    diff_scope_class: str,
    workflow_repository: str,
    workflow_run_id: int,
    workflow_ref: str,
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
    provenance = _workflow_provenance(
        workflow_repository,
        workflow_run_id,
        workflow_ref,
    )
    canonical = json.dumps(
        {
            "pr_number": pr_number,
            "exact_head_sha": exact_head_sha,
            "changed_paths": canonical_paths,
            "changed_paths_sha256": changed_paths_sha256(canonical_paths),
            "protected_paths": _canonical_protected_paths(canonical_paths),
            "diff_scope_class": diff_scope_class,
            "review_scope_policy_version": policy_version,
            "review_scope_policy_sha256": review_scope_policy_sha256(policy_version),
            "workflow_provenance": provenance,
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
    expected_workflow_repository: str | None = None,
    expected_workflow_run_id: int | None = None,
    expected_workflow_ref: str | None = None,
) -> None:
    # A receipt is never allowed to authenticate its own context. Callers must
    # supply PR/head/diff and GitHub workflow provenance from a trusted source.
    if (
        expected_pr_number is None
        or expected_head_sha is None
        or expected_changed_paths is None
        or expected_diff_scope is None
        or expected_workflow_repository is None
        or expected_workflow_run_id is None
        or expected_workflow_ref is None
    ):
        raise RuntimeError("trusted review context and workflow provenance required")

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
    trusted_protected = list(_canonical_protected_paths(trusted_paths))
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
    if receipt.get("protected_paths") != trusted_protected:
        raise RuntimeError("protected-path context mismatch")
    if receipt.get("diff_scope_class") != trusted_scope or receipt.get("diff_scope_class") != expected_diff_scope:
        raise RuntimeError("diff-scope classification mismatch")
    if receipt.get("integration_authority") != "NONE":
        raise RuntimeError("review receipt must not grant integration authority")

    trusted_provenance = _workflow_provenance(
        expected_workflow_repository,
        expected_workflow_run_id,
        expected_workflow_ref,
    )
    if receipt.get("workflow_provenance") != trusted_provenance:
        raise RuntimeError("workflow provenance mismatch")

    expected_context_sha = review_receipt_context_sha256(
        pr_number=expected_pr_number,
        exact_head_sha=expected_head_sha,
        changed_paths=trusted_paths,
        diff_scope_class=expected_diff_scope,
        workflow_repository=expected_workflow_repository,
        workflow_run_id=expected_workflow_run_id,
        workflow_ref=expected_workflow_ref,
        policy_version=version,
    )
    if receipt.get("review_context_sha256") != expected_context_sha:
        raise RuntimeError("review trusted-context digest mismatch")

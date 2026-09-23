from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from orchestration.protected_paths import DEFAULT_PATH, find_protected_matches, load_protected_paths
from orchestration.reviewer_trust_root import reviewer_trust_root_identity

REVIEW_SCOPE_POLICY_VERSION = 8
REVIEW_RECEIPT_SCHEMA_VERSION = 7
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Policy v6's exact allowlist is historical lineage. Do not mutate it when the
# current reviewer grows new trust-root code/tests.
_V6_REVIEW_INFRASTRUCTURE_PATHS = frozenset(
    {
        "orchestration/exact_head_review.py",
        "orchestration/review_scope_policy.py",
        "tests/test_exact_head_review.py",
        "tests/test_review_scope_policy.py",
    }
)
_V5_REVIEW_INFRASTRUCTURE_PATHS = _V6_REVIEW_INFRASTRUCTURE_PATHS

# Current review-infrastructure scope includes the machine-readable trust root,
# its verifier, canonical review workflow and reviewer-specific regression/threat-
# model companions. A ledger-only/docs-only change is never REVIEW_INFRASTRUCTURE
# because classify_diff_scope() also requires one CORE path to change.
REVIEW_INFRASTRUCTURE_CORE_PATHS = frozenset(
    {
        "orchestration/exact_head_review.py",
        "orchestration/review_scope_policy.py",
        "orchestration/reviewer_trust_root.py",
        "orchestration/reviewer_trust_root.json",
        ".github/workflows/exact_head_independent_review.yml",
    }
)
REVIEW_INFRASTRUCTURE_PATHS = frozenset(
    set(REVIEW_INFRASTRUCTURE_CORE_PATHS)
    | {
        "tests/test_exact_head_review.py",
        "tests/test_exact_head_review_nonverdict_bootstrap.py",
        "tests/test_exact_head_review_wait_authority_contract.py",
        "tests/test_exact_head_review_workflow.py",
        "tests/test_review_scope_policy.py",
        "tests/test_reviewer_trust_root.py",
        "BUG_REGRESSION_LEDGER.md",
    }
)
# Freeze v7's exact scope sets so v8 is append-only lineage rather than a
# reinterpretation of the predecessor policy identity.
_V7_REVIEW_INFRASTRUCTURE_CORE_PATHS = frozenset(REVIEW_INFRASTRUCTURE_CORE_PATHS)
_V7_REVIEW_INFRASTRUCTURE_PATHS = frozenset(REVIEW_INFRASTRUCTURE_PATHS)

# Version 5 is retained byte-for-byte as historical lineage. New policy versions
# are additive registrations rather than reinterpretations of old receipts.
_REVIEW_SCOPE_DISCIPLINE_V5 = (
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

_REVIEW_SCOPE_DISCIPLINE_V6 = (
    _REVIEW_SCOPE_DISCIPLINE_V5
    + " REVIEW_PROVENANCE_V6: bind every production receipt to the exact reviewer-runtime Git SHA and the explicit "
      "version+digest identity of the canonical protected-path registry. A workflow run id/ref without the runtime SHA "
      "is insufficient provenance. Policy lineage is append-only: the immediately prior registered policy digest is "
      "committed into the new policy identity, so a new version cannot silently reinterpret an earlier receipt. "
      "Same-version protected-registry drift fails closed and requires a new policy version before review can proceed. "
      "GitHub's durable workflow run plus review-attempt issue provide the server-authored causal/audit trail; the JSON "
      "receipt remains non-authoritative unless a consumer independently supplies matching PR/head/diff, workflow run/ref, "
      "reviewer-runtime SHA, and protected-registry identity."
)

_REVIEW_SCOPE_DISCIPLINE_V7 = (
    _REVIEW_SCOPE_DISCIPLINE_V6
    + " REVIEW_TRUST_ROOT_V7: the reviewer trust root is machine-readable and policy-bound. Production review execution "
      "must independently reconcile GitHub-hosted runner identity, exact workflow path/ref/SHA, run id+attempt+event, "
      "checked-out runtime SHA, server-observed Actions run metadata, and server-observed canonical-main SHA before any "
      "reviewer provider is invoked. Environment variables alone are insufficient. GitHub.com control-plane or hosted-"
      "runner compromise and intentional repository-admin rewrites remain explicitly out of scope rather than falsely "
      "claimed as cryptographically solved. Receipt integrity is not approval: approve=false remains a valid terminal "
      "review record but can never be consumed through the approval verifier, and every receipt still carries integration "
      "authority NONE. Receipt-schema/policy lineage is historical-only across versions; an older approval cannot be "
      "silently reinterpreted under the current trust policy. Active protected-registry drift must fail before model "
      "execution."
)

REVIEW_SCOPE_DISCIPLINE = (
    _REVIEW_SCOPE_DISCIPLINE_V7
    + " REVIEW_TRUST_ROOT_V8: trusted server observations for this public repository are fetched without the workflow-"
      "issued GitHub token, so compromise of that token alone cannot forge the run/ref/workflow evidence used by the "
      "receipt binding. The exact canonical review workflow source is frozen by Git blob identity and reconciled byte-for-"
      "byte plus SHA256 between the checked-out runtime and GitHub's public server view before reviewer execution. The "
      "v8 trust root cryptographically names its v7 predecessor, while v7 policy and receipt identities remain historical "
      "and non-reusable. Any active trust-root/workflow/registry drift fails closed and requires a new policy version plus "
      "fresh independent review. These controls still grant no integration, promotion, broker, protected-OOS, or trading "
      "authority."
)

REVIEW_SCOPE_POLICIES: dict[int, str] = {
    5: _REVIEW_SCOPE_DISCIPLINE_V5,
    6: _REVIEW_SCOPE_DISCIPLINE_V6,
    7: _REVIEW_SCOPE_DISCIPLINE_V7,
    REVIEW_SCOPE_POLICY_VERSION: REVIEW_SCOPE_DISCIPLINE,
}

# The v5 policy used the then-current registry patterns directly in its digest.
# Freeze them here so the historical v5 digest cannot drift when the live registry changes.
_V5_PROTECTED_PATH_PATTERNS = (
    "AI_STATE.md",
    "AGENTS.md",
    "docs/CHATGPT_SPECIALISTS.md",
    "docs/MULTI_ENGINE_PROTOCOL.md",
    "agents/*",
    "orchestration/*",
    ".github/workflows/*",
    "requirements.txt",
    "Dockerfile",
    "live_promotions.json",
    "resource_recommendations_decisions.json",
    "BUG_REGRESSION_LEDGER.md",
    "fleet_coordination.json",
    ".env*",
    "**/.env*",
)

# v6-v8 are authorized only against this exact registry identity. A registry
# change requires a new policy version and fresh independent review.
_V6_PROTECTED_REGISTRY = {
    "version": 1,
    "sha256": "00e9f1a404d1f5b92210f0c172295cd0067ff1078c33e4dcb284a4e3be4c7f25",
}
_V7_PROTECTED_REGISTRY = dict(_V6_PROTECTED_REGISTRY)
_V8_PROTECTED_REGISTRY = dict(_V7_PROTECTED_REGISTRY)
_V7_REVIEWER_TRUST_ROOT = {
    "schema_version": 1,
    "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V1",
    "sha256": "53c96f8eca58aba2f5242c858c766b5b4ca65d93839aa9734338ee3de0aebe3f",
}
_V8_REVIEWER_TRUST_ROOT = {
    "schema_version": 2,
    "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V2",
    "sha256": "5cf45d9cd44a8728ecd894fcfc1d79d9f43c0dfb24a579ed688dc5f800ec86dc",
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


def protected_path_registry_identity() -> dict[str, Any]:
    payload = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    version = payload.get("version")
    patterns = payload.get("patterns")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise RuntimeError("protected-path registry version is invalid")
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(pattern, str) and pattern for pattern in patterns)
    ):
        raise RuntimeError("protected-path registry patterns are invalid")
    if tuple(patterns) != load_protected_paths():
        raise RuntimeError("protected-path registry loader mismatch")
    canonical = json.dumps(
        {"version": version, "patterns": patterns},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return {
        "version": version,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _expected_registry_identity(version: int) -> dict[str, Any]:
    if version == 5:
        canonical = json.dumps(
            {"version": 1, "patterns": list(_V5_PROTECTED_PATH_PATTERNS)},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return {
            "version": 1,
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }
    if version == 6:
        return dict(_V6_PROTECTED_REGISTRY)
    if version == 7:
        return dict(_V7_PROTECTED_REGISTRY)
    if version == REVIEW_SCOPE_POLICY_VERSION:
        return dict(_V8_PROTECTED_REGISTRY)
    raise RuntimeError("unknown review-scope policy version")


def _expected_trust_root_identity(version: int) -> dict[str, Any]:
    if version == 7:
        return dict(_V7_REVIEWER_TRUST_ROOT)
    if version == REVIEW_SCOPE_POLICY_VERSION:
        return dict(_V8_REVIEWER_TRUST_ROOT)
    raise RuntimeError("reviewer trust root is unavailable for historical policy")


def _assert_active_registry_matches_policy(version: int = REVIEW_SCOPE_POLICY_VERSION) -> dict[str, Any]:
    actual = protected_path_registry_identity()
    expected = _expected_registry_identity(version)
    if actual != expected:
        raise RuntimeError(
            "protected-path registry identity drifted from the active review policy; "
            "a new policy version and independent review are required"
        )
    return actual


def _assert_active_trust_root_matches_policy(version: int = REVIEW_SCOPE_POLICY_VERSION) -> dict[str, Any]:
    actual = reviewer_trust_root_identity()
    expected = _expected_trust_root_identity(version)
    if actual != expected:
        raise RuntimeError(
            "reviewer trust-root identity drifted from the active review policy; "
            "a new policy version and independent review are required"
        )
    return actual


def _workflow_provenance(
    repository: str,
    run_id: int,
    workflow_ref: str,
    runtime_git_sha: str,
) -> dict[str, Any]:
    if not isinstance(repository, str) or _REPO_RE.fullmatch(repository) is None:
        raise RuntimeError("invalid trusted workflow repository")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise RuntimeError("invalid trusted workflow run id")
    if not isinstance(workflow_ref, str) or not workflow_ref.strip() or len(workflow_ref) > 1024:
        raise RuntimeError("invalid trusted workflow ref")
    if not isinstance(runtime_git_sha, str) or not _SHA_RE.fullmatch(runtime_git_sha):
        raise RuntimeError("invalid trusted reviewer-runtime git SHA")
    return {
        "repository": repository,
        "run_id": run_id,
        "workflow_ref": workflow_ref.strip(),
        "runtime_git_sha": runtime_git_sha,
    }


def review_scope_policy_sha256(version: int = REVIEW_SCOPE_POLICY_VERSION) -> str:
    discipline = REVIEW_SCOPE_POLICIES.get(version)
    if discipline is None:
        raise RuntimeError("unknown review-scope policy version")
    if version == 5:
        payload = {
            "version": version,
            "discipline": discipline,
            "review_infrastructure_paths": sorted(_V5_REVIEW_INFRASTRUCTURE_PATHS),
            "protected_path_patterns": list(_V5_PROTECTED_PATH_PATTERNS),
        }
    elif version == 6:
        payload = {
            "version": version,
            "discipline": discipline,
            "review_infrastructure_paths": sorted(_V6_REVIEW_INFRASTRUCTURE_PATHS),
            "protected_path_registry": _expected_registry_identity(version),
            "parent_policy": {
                "version": 5,
                "sha256": review_scope_policy_sha256(5),
            },
        }
    elif version == 7:
        payload = {
            "version": version,
            "discipline": discipline,
            "review_infrastructure_paths": sorted(_V7_REVIEW_INFRASTRUCTURE_PATHS),
            "review_infrastructure_core_paths": sorted(_V7_REVIEW_INFRASTRUCTURE_CORE_PATHS),
            "protected_path_registry": _expected_registry_identity(version),
            "reviewer_trust_root": _expected_trust_root_identity(version),
            "parent_policy": {
                "version": 6,
                "sha256": review_scope_policy_sha256(6),
            },
        }
    else:
        _assert_active_registry_matches_policy(version)
        trust_root = _assert_active_trust_root_matches_policy(version)
        payload = {
            "version": version,
            "discipline": discipline,
            "review_infrastructure_paths": sorted(REVIEW_INFRASTRUCTURE_PATHS),
            "review_infrastructure_core_paths": sorted(REVIEW_INFRASTRUCTURE_CORE_PATHS),
            "protected_path_registry": _expected_registry_identity(version),
            "reviewer_trust_root": trust_root,
            "parent_policy": {
                "version": 7,
                "sha256": review_scope_policy_sha256(7),
            },
        }
    canonical = json.dumps(
        payload,
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
    if (
        all(path in REVIEW_INFRASTRUCTURE_PATHS for path in paths)
        and any(path in REVIEW_INFRASTRUCTURE_CORE_PATHS for path in paths)
    ):
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
    workflow_runtime_sha: str,
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
        workflow_runtime_sha,
    )
    registry_identity = _assert_active_registry_matches_policy(policy_version)
    trust_root_identity = _assert_active_trust_root_matches_policy(policy_version)
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
            "protected_path_registry": registry_identity,
            "reviewer_trust_root": trust_root_identity,
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
    expected_workflow_runtime_sha: str | None = None,
) -> None:
    # A receipt is never allowed to authenticate its own context. Callers must
    # supply PR/head/diff plus GitHub workflow/runtime provenance from a trusted source.
    if (
        expected_pr_number is None
        or expected_head_sha is None
        or expected_changed_paths is None
        or expected_diff_scope is None
        or expected_workflow_repository is None
        or expected_workflow_run_id is None
        or expected_workflow_ref is None
        or expected_workflow_runtime_sha is None
    ):
        raise RuntimeError("trusted review context, workflow provenance, and runtime SHA required")

    schema_version = receipt.get("review_receipt_schema_version")
    if isinstance(schema_version, bool) or schema_version != REVIEW_RECEIPT_SCHEMA_VERSION:
        raise RuntimeError("unsupported review receipt schema version")
    if receipt.get("review_scope") != "READ_ONLY_EXACT_HEAD":
        raise RuntimeError("invalid review scope")
    version = receipt.get("review_scope_policy_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise RuntimeError("invalid review-scope policy version")
    if version != REVIEW_SCOPE_POLICY_VERSION:
        raise RuntimeError("stale review-scope policy version")
    expected_policy_sha = review_scope_policy_sha256(version)
    if receipt.get("review_scope_policy_sha256") != expected_policy_sha:
        raise RuntimeError("review-scope policy digest mismatch")

    trusted_registry = _assert_active_registry_matches_policy(version)
    if receipt.get("protected_path_registry") != trusted_registry:
        raise RuntimeError("protected-path registry identity mismatch")
    trusted_root = _assert_active_trust_root_matches_policy(version)
    if receipt.get("reviewer_trust_root") != trusted_root:
        raise RuntimeError("reviewer trust-root identity mismatch")

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
        expected_workflow_runtime_sha,
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
        workflow_runtime_sha=expected_workflow_runtime_sha,
        policy_version=version,
    )
    if receipt.get("review_context_sha256") != expected_context_sha:
        raise RuntimeError("review trusted-context digest mismatch")

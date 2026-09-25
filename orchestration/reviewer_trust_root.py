from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

TRUST_ROOT_PATH = Path(__file__).with_name("reviewer_trust_root.json")
TRUST_BINDING_VERSION = 2
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PARENT_TRUST_ROOT = {
    "schema_version": 1,
    "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V1",
    "sha256": "53c96f8eca58aba2f5242c858c766b5b4ca65d93839aa9734338ee3de0aebe3f",
}


def _strict_object(raw: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise RuntimeError("reviewer trust root must be one JSON object")
    return value


def load_reviewer_trust_root(path: Path = TRUST_ROOT_PATH) -> dict[str, Any]:
    try:
        root = _strict_object(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("unable to load reviewer trust root") from exc

    required = {
        "schema_version",
        "trust_boundary_id",
        "platform",
        "repository",
        "workflow_path",
        "workflow_ref",
        "workflow_source",
        "api_base_url",
        "required_runner_environment",
        "required_github_actions",
        "trusted_control_plane",
        "required_observations",
        "out_of_scope_platform_compromise",
        "parent_trust_root",
        "authority",
    }
    if set(root) != required:
        raise RuntimeError("reviewer trust root key set mismatch")
    if root["schema_version"] != 2 or isinstance(root["schema_version"], bool):
        raise RuntimeError("unsupported reviewer trust root schema")
    if root["trust_boundary_id"] != "EXACT_HEAD_REVIEW_TRUST_ROOT_V2":
        raise RuntimeError("unexpected reviewer trust boundary id")
    if root["platform"] != "github.com":
        raise RuntimeError("unsupported review platform")
    if not isinstance(root["repository"], str) or _REPO_RE.fullmatch(root["repository"]) is None:
        raise RuntimeError("invalid trust-root repository")
    if root["workflow_path"] != ".github/workflows/exact_head_independent_review.yml":
        raise RuntimeError("unexpected trusted review workflow path")
    if root["workflow_ref"] != "refs/heads/main":
        raise RuntimeError("trusted review workflow must run from canonical main")
    workflow_source = root["workflow_source"]
    if not isinstance(workflow_source, dict) or set(workflow_source) != {"git_blob_sha", "binding"}:
        raise RuntimeError("invalid trusted workflow-source binding")
    if _SHA_RE.fullmatch(str(workflow_source.get("git_blob_sha", ""))) is None:
        raise RuntimeError("invalid trusted workflow Git blob SHA")
    if workflow_source.get("binding") != "git_blob_sha_plus_runtime_sha256":
        raise RuntimeError("unexpected workflow-source binding mode")
    if root["api_base_url"] != "https://api.github.com":
        raise RuntimeError("unexpected trusted GitHub API base URL")
    if root["required_runner_environment"] != "github-hosted":
        raise RuntimeError("review trust root must require a GitHub-hosted runner")
    if root["required_github_actions"] is not True:
        raise RuntimeError("review trust root must require GitHub Actions")
    for key in ("trusted_control_plane", "required_observations", "out_of_scope_platform_compromise"):
        values = root[key]
        if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values):
            raise RuntimeError(f"invalid reviewer trust-root list: {key}")
    if root["parent_trust_root"] != _PARENT_TRUST_ROOT:
        raise RuntimeError("reviewer trust-root lineage drift")
    authority = root["authority"]
    if not isinstance(authority, dict):
        raise RuntimeError("invalid reviewer trust-root authority")
    if authority != {
        "review_receipt_is_authentication_token": False,  # nosec B105
        "approval_receipt_grants_integration": False,
        "integration_authority": "NONE",
        "broker_authority": False,
        "trading_authority": False,
        "protected_oos_authority": False,
    }:
        raise RuntimeError("reviewer trust-root authority drift")
    return root


def reviewer_trust_root_identity(path: Path = TRUST_ROOT_PATH) -> dict[str, Any]:
    root = load_reviewer_trust_root(path)
    canonical = json.dumps(root, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": root["schema_version"],
        "trust_boundary_id": root["trust_boundary_id"],
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"trusted GitHub workflow environment missing {name}")
    return value


def _positive_int(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"invalid {label}") from exc
    if value <= 0:
        raise RuntimeError(f"invalid {label}")
    return value


def _github_public_api_json(url: str) -> dict[str, Any]:
    """Read public GitHub server state without the workflow-issued token.

    The repository is public. Keeping this observation path unauthenticated makes
    a compromised workflow GH_TOKEN/GITHUB_TOKEN unable, by itself, to forge the
    server observations used by the receipt trust binding. GitHub control-plane
    compromise remains explicitly outside the declared threat model.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tradingview-ai-crypto-exact-head-review",
    }
    try:
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=False)
        response.raise_for_status()
        value = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError("trusted public GitHub API observation unavailable") from exc
    if not isinstance(value, dict):
        raise RuntimeError("trusted public GitHub API observation must be an object")
    return value


def _git_blob_sha(data: bytes) -> str:
    payload = f"blob {len(data)}\0".encode("ascii") + data
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()  # nosec B324 - Git object identity


def _workflow_bytes(root: dict[str, Any]) -> bytes:
    path = Path(__file__).resolve().parents[1] / root["workflow_path"]
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RuntimeError("trusted workflow source is unavailable locally") from exc


def _server_workflow_bytes(payload: dict[str, Any]) -> bytes:
    if payload.get("type") != "file" or payload.get("encoding") != "base64":
        raise RuntimeError("trusted server workflow source is not an inline base64 file")
    raw = payload.get("content")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError("trusted server workflow source content missing")
    normalized = raw.replace("\n", "").replace("\r", "")
    try:
        return base64.b64decode(normalized, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("trusted server workflow source base64 invalid") from exc


def collect_trusted_workflow_context(*, runtime_git_sha: str) -> dict[str, Any]:
    """Bind reviewer execution to public server-observed Actions/main/workflow identities.

    This intentionally fails closed if canonical main advances while the review is
    executing or if the exact review workflow differs from the independently
    reviewed workflow object frozen in the trust root. A fresh queue attempt on a
    new canonical state is safer than treating stale provenance as approval.
    """
    root = load_reviewer_trust_root()
    if not isinstance(runtime_git_sha, str) or _SHA_RE.fullmatch(runtime_git_sha) is None:
        raise RuntimeError("invalid reviewer-runtime git SHA")

    if _required_env("GITHUB_ACTIONS").lower() != "true":
        raise RuntimeError("review execution is not inside GitHub Actions")
    if _required_env("RUNNER_ENVIRONMENT") != root["required_runner_environment"]:
        raise RuntimeError("review execution is not on the trusted runner class")

    repository = _required_env("GITHUB_REPOSITORY")
    if repository != root["repository"]:
        raise RuntimeError("workflow repository does not match reviewer trust root")
    run_id = _positive_int(_required_env("GITHUB_RUN_ID"), "GitHub workflow run id")
    run_attempt = _positive_int(_required_env("GITHUB_RUN_ATTEMPT"), "GitHub workflow run attempt")
    event_name = _required_env("GITHUB_EVENT_NAME")
    if event_name not in {"issues", "schedule", "workflow_dispatch"}:
        raise RuntimeError("untrusted review workflow event")

    workflow_ref = _required_env("GITHUB_WORKFLOW_REF")
    expected_workflow_ref = f"{repository}/{root['workflow_path']}@{root['workflow_ref']}"
    if workflow_ref != expected_workflow_ref:
        raise RuntimeError("review workflow ref does not match trust root")

    workflow_sha = _required_env("GITHUB_WORKFLOW_SHA")
    github_sha = _required_env("GITHUB_SHA")
    github_ref = _required_env("GITHUB_REF")
    if github_ref != root["workflow_ref"]:
        raise RuntimeError("review workflow is not executing from canonical main ref")
    for label, sha in (("workflow SHA", workflow_sha), ("GitHub SHA", github_sha)):
        if _SHA_RE.fullmatch(sha) is None:
            raise RuntimeError(f"invalid trusted {label}")
        if sha != runtime_git_sha:
            raise RuntimeError(f"trusted {label} does not match reviewer runtime")

    local_workflow = _workflow_bytes(root)
    local_workflow_blob_sha = _git_blob_sha(local_workflow)
    local_workflow_sha256 = hashlib.sha256(local_workflow).hexdigest()
    expected_workflow_blob_sha = root["workflow_source"]["git_blob_sha"]
    if local_workflow_blob_sha != expected_workflow_blob_sha:
        raise RuntimeError("local review workflow source drifted from the trust root")

    api = root["api_base_url"]
    run = _github_public_api_json(f"{api}/repos/{repository}/actions/runs/{run_id}")
    main_ref = _github_public_api_json(f"{api}/repos/{repository}/git/ref/heads/main")

    if run.get("id") != run_id:
        raise RuntimeError("GitHub run identity mismatch")
    server_repository = run.get("repository")
    if not isinstance(server_repository, dict) or server_repository.get("full_name") != repository:
        raise RuntimeError("GitHub run repository mismatch")
    if run.get("path") != root["workflow_path"]:
        raise RuntimeError("GitHub run workflow path mismatch")
    if run.get("event") != event_name:
        raise RuntimeError("GitHub run event mismatch")
    if run.get("run_attempt") != run_attempt:
        raise RuntimeError("GitHub run attempt mismatch")
    if run.get("head_branch") != "main":
        raise RuntimeError("GitHub run did not execute from main")
    server_run_head_sha = run.get("head_sha")
    if not isinstance(server_run_head_sha, str) or _SHA_RE.fullmatch(server_run_head_sha) is None:
        raise RuntimeError("invalid GitHub run head SHA")
    if server_run_head_sha != runtime_git_sha:
        raise RuntimeError("GitHub run head does not match reviewer runtime")

    ref_object = main_ref.get("object")
    server_main_sha = ref_object.get("sha") if isinstance(ref_object, dict) else None
    if not isinstance(server_main_sha, str) or _SHA_RE.fullmatch(server_main_sha) is None:
        raise RuntimeError("invalid canonical-main server SHA")
    if server_main_sha != runtime_git_sha:
        raise RuntimeError("canonical main advanced during reviewer execution; retry on current main")

    server_workflow = _github_public_api_json(
        f"{api}/repos/{repository}/contents/{root['workflow_path']}?ref={server_main_sha}"
    )
    server_workflow_blob_sha = server_workflow.get("sha")
    if server_workflow_blob_sha != expected_workflow_blob_sha:
        raise RuntimeError("server review workflow source drifted from the trust root")
    server_workflow_bytes = _server_workflow_bytes(server_workflow)
    if _git_blob_sha(server_workflow_bytes) != server_workflow_blob_sha:
        raise RuntimeError("server review workflow content does not match its Git blob identity")
    server_workflow_sha256 = hashlib.sha256(server_workflow_bytes).hexdigest()
    if server_workflow_bytes != local_workflow or server_workflow_sha256 != local_workflow_sha256:
        raise RuntimeError("local and server review workflow sources differ")
    if _SHA256_RE.fullmatch(server_workflow_sha256) is None:
        raise RuntimeError("invalid trusted workflow SHA256")

    context = {
        "repository": repository,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "event_name": event_name,
        "workflow_ref": workflow_ref,
        "workflow_sha": workflow_sha,
        "runtime_git_sha": runtime_git_sha,
        "github_sha": github_sha,
        "server_run_head_sha": server_run_head_sha,
        "server_run_event": run.get("event"),
        "server_run_attempt": run.get("run_attempt"),
        "server_run_path": run.get("path"),
        "server_main_sha": server_main_sha,
        "local_workflow_blob_sha": local_workflow_blob_sha,
        "local_workflow_sha256": local_workflow_sha256,
        "server_workflow_blob_sha": server_workflow_blob_sha,
        "server_workflow_sha256": server_workflow_sha256,
        "server_observation_auth": "PUBLIC_UNAUTHENTICATED_GITHUB_API",
    }
    if set(context) != set(root["required_observations"]):
        raise RuntimeError("trusted workflow observation set drift")
    return context


def workflow_trust_context_sha256(context: dict[str, Any]) -> str:
    root = load_reviewer_trust_root()
    if not isinstance(context, dict) or set(context) != set(root["required_observations"]):
        raise RuntimeError("trusted workflow context key set mismatch")
    canonical = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seal_review_receipt_trust(receipt: dict[str, Any], *, trusted_context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise RuntimeError("review receipt must be an object")
    sealed = dict(receipt)
    root_identity = reviewer_trust_root_identity()
    context = dict(trusted_context)
    context_digest = workflow_trust_context_sha256(context)
    sealed.update(
        {
            "review_trust_binding_version": TRUST_BINDING_VERSION,
            "reviewer_trust_root": root_identity,
            "workflow_trust_context": context,
            "workflow_trust_context_sha256": context_digest,
            "approval_consumption": {
                "integrity_verification_is_approval": False,
                "approve_true_required": True,
                "integration_authority": "NONE",
            },
        }
    )
    verdict_payload = {
        "review_context_sha256": sealed.get("review_context_sha256"),
        "reviewer_trust_root": root_identity,
        "workflow_trust_context_sha256": context_digest,
        "approve": sealed.get("approve"),
        "risk": sealed.get("risk"),
        "reason": sealed.get("reason"),
        "integration_authority": sealed.get("integration_authority"),
    }
    canonical = json.dumps(verdict_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    sealed["review_trust_binding_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return sealed


def receipt_lineage_status(receipt: dict[str, Any], *, current_schema_version: int) -> str:
    if not isinstance(receipt, dict):
        return "INVALID"
    schema = receipt.get("review_receipt_schema_version")
    binding = receipt.get("review_trust_binding_version")
    if schema != current_schema_version or binding != TRUST_BINDING_VERSION:
        return "HISTORICAL_ONLY_NOT_APPROVAL"
    return "CURRENT_TRUST_BOUND"


def verify_trust_bound_review_receipt(
    receipt: dict[str, Any],
    *,
    trusted_context: dict[str, Any],
    current_schema_version: int,
    require_approval: bool,
) -> None:
    if receipt_lineage_status(receipt, current_schema_version=current_schema_version) != "CURRENT_TRUST_BOUND":
        raise RuntimeError("historical review receipt cannot be consumed as current approval")
    if receipt.get("integration_authority") != "NONE":
        raise RuntimeError("review receipt must not grant integration authority")
    if receipt.get("reviewer_trust_root") != reviewer_trust_root_identity():
        raise RuntimeError("reviewer trust-root identity mismatch")
    expected_context = dict(trusted_context)
    if receipt.get("workflow_trust_context") != expected_context:
        raise RuntimeError("trusted workflow context mismatch")
    expected_context_digest = workflow_trust_context_sha256(expected_context)
    if receipt.get("workflow_trust_context_sha256") != expected_context_digest:
        raise RuntimeError("trusted workflow context digest mismatch")
    if receipt.get("approval_consumption") != {
        "integrity_verification_is_approval": False,
        "approve_true_required": True,
        "integration_authority": "NONE",
    }:
        raise RuntimeError("review approval-consumption semantics mismatch")
    verdict_payload = {
        "review_context_sha256": receipt.get("review_context_sha256"),
        "reviewer_trust_root": receipt.get("reviewer_trust_root"),
        "workflow_trust_context_sha256": receipt.get("workflow_trust_context_sha256"),
        "approve": receipt.get("approve"),
        "risk": receipt.get("risk"),
        "reason": receipt.get("reason"),
        "integration_authority": receipt.get("integration_authority"),
    }
    canonical = json.dumps(verdict_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected_binding = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if receipt.get("review_trust_binding_sha256") != expected_binding:
        raise RuntimeError("review trust binding digest mismatch")
    if require_approval and receipt.get("approve") is not True:
        raise RuntimeError("integrity-valid rejection cannot be consumed as approval")

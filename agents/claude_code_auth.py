from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SUBSCRIPTION = "SUBSCRIPTION"
API_METERED = "API_METERED"
MANUAL_ADAPTER_REQUIRED = "MANUAL_ADAPTER_REQUIRED"
UNKNOWN = "UNKNOWN"
SUBSCRIPTION_AUTOMATED = "SUBSCRIPTION_AUTOMATED"

REPO = "rnnyrgs-web/tradingview-ai-crypto"
CAPABILITY_WORKFLOW = ".github/workflows/claude_code_subscription_probe.yml"
SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_AUTH_MODES = {SUBSCRIPTION, API_METERED, MANUAL_ADAPTER_REQUIRED, UNKNOWN}
SECRET_ENV_NAMES = {"CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"}
DIRECT_MAIN_BRANCHES = {"main", "master", "refs/heads/main", "refs/heads/master"}


class AuthPolicyError(RuntimeError):
    pass


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def _validate_branch_identity(branch: Any) -> str:
    if not isinstance(branch, str) or not branch:
        raise AuthPolicyError("branch identity must be non-empty")
    if branch != branch.strip():
        raise AuthPolicyError("branch identity must not contain surrounding whitespace")
    if branch in DIRECT_MAIN_BRANCHES:
        raise AuthPolicyError("adapter attempt cannot target main")
    return branch


@dataclass(frozen=True)
class AuthDecision:
    auth_mode: str
    execute: bool
    credential_ref: str | None
    budget_gate_required: bool
    capability_proven: bool
    capability_proof_ref: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        validate_decision(result)
        return result


def validate_capability_receipt(
    receipt: Mapping[str, Any], *, trusted_workflow_sha: str
) -> str:
    """Validate the durable GitHub Actions proof used to authorize subscription mode.

    A caller cannot authorize subscription execution with a boolean or arbitrary
    proof string. It must supply the exact secret-free receipt emitted by the
    pinned capability workflow, and the orchestrator must bind that receipt to a
    workflow SHA it independently trusts (normally the current reviewed main
    SHA after this workflow has been integrated).

    This validation does not itself query GitHub. The orchestration boundary is
    responsible for obtaining the receipt and trusted SHA from GitHub rather
    than caller-authored state.
    """
    if not isinstance(receipt, Mapping):
        raise AuthPolicyError("capability receipt must be a mapping")
    if not _valid_sha(trusted_workflow_sha):
        raise AuthPolicyError("trusted workflow SHA must be a lowercase 40-character SHA")

    required = {
        "version",
        "provider",
        "engine",
        "auth_mode",
        "reason",
        "repository",
        "run_id",
        "run_attempt",
        "event_name",
        "head_sha",
        "execution_sha",
        "workflow_ref",
        "probe_step_outcome",
        "probe_conclusion",
        "structured_probe_verified",
        "proof_ref",
        "content_digest",
    }
    if set(receipt) != required:
        raise AuthPolicyError("capability receipt fields mismatch")
    if receipt.get("version") != 3:
        raise AuthPolicyError("unsupported capability receipt version")
    if receipt.get("provider") != "anthropic" or receipt.get("engine") != "claude-code":
        raise AuthPolicyError("capability provider/engine mismatch")
    if receipt.get("auth_mode") != SUBSCRIPTION_AUTOMATED:
        raise AuthPolicyError("capability receipt does not prove subscription automation")
    if receipt.get("reason") != "OFFICIAL_OAUTH_ACTION_STRUCTURED_PROBE_SUCCEEDED":
        raise AuthPolicyError("capability success reason mismatch")
    if receipt.get("repository") != REPO:
        raise AuthPolicyError("capability repository mismatch")
    if receipt.get("event_name") != "workflow_dispatch":
        raise AuthPolicyError("capability event must be trusted-main workflow_dispatch")
    if receipt.get("head_sha") != trusted_workflow_sha:
        raise AuthPolicyError("capability proof is not bound to trusted workflow SHA")
    if receipt.get("execution_sha") != trusted_workflow_sha:
        raise AuthPolicyError("capability execution SHA is not bound to trusted workflow SHA")
    if receipt.get("probe_step_outcome") != "success" or receipt.get("probe_conclusion") != "success":
        raise AuthPolicyError("capability action did not succeed")
    if receipt.get("structured_probe_verified") is not True:
        raise AuthPolicyError("capability structured model proof missing")

    run_id = str(receipt.get("run_id") or "")
    run_attempt = str(receipt.get("run_attempt") or "")
    if not run_id.isdigit() or int(run_id) <= 0 or not run_attempt.isdigit() or int(run_attempt) <= 0:
        raise AuthPolicyError("malformed capability run identity")
    expected_proof = f"github-actions://{REPO}/runs/{run_id}/attempts/{run_attempt}"
    if receipt.get("proof_ref") != expected_proof:
        raise AuthPolicyError("capability proof reference mismatch")

    workflow_ref = receipt.get("workflow_ref")
    expected_workflow_ref = f"{REPO}/{CAPABILITY_WORKFLOW}@refs/heads/main"
    if workflow_ref != expected_workflow_ref:
        raise AuthPolicyError("capability workflow identity mismatch")

    unsigned = {k: v for k, v in receipt.items() if k != "content_digest"}
    if receipt.get("content_digest") != _digest(unsigned):
        raise AuthPolicyError("capability receipt digest mismatch")

    raw = json.dumps(dict(receipt), sort_keys=True)
    for secret_name in SECRET_ENV_NAMES:
        secret_value = os.environ.get(secret_name)
        if secret_value and secret_value in raw:
            raise AuthPolicyError("credential value leaked into capability receipt")
    return expected_proof


def resolve_auth(
    *,
    oauth_present: bool,
    api_key_present: bool,
    capability_receipt: Mapping[str, Any] | None = None,
    trusted_workflow_sha: str | None = None,
    allow_api_fallback: bool = True,
) -> AuthDecision:
    """Select authentication without accepting or returning credential values.

    Credential presence is deliberately not proof of a supported autonomous
    subscription path. Subscription execution requires the exact durable
    capability receipt plus a separately trusted workflow SHA. There is no
    boolean/self-asserted escape hatch.
    """
    capability_proof_ref: str | None = None
    if capability_receipt is not None:
        if not oauth_present:
            raise AuthPolicyError("subscription capability cannot be used without OAuth credential presence")
        if trusted_workflow_sha is None:
            raise AuthPolicyError("capability receipt requires trusted workflow SHA")
        capability_proof_ref = validate_capability_receipt(
            capability_receipt, trusted_workflow_sha=trusted_workflow_sha
        )
    elif trusted_workflow_sha is not None:
        raise AuthPolicyError("trusted workflow SHA cannot authorize subscription without capability receipt")

    if oauth_present:
        if capability_proof_ref is None:
            # Never silently switch to paid API when the caller is explicitly
            # configured for subscription OAuth but that path is not yet proven.
            return AuthDecision(
                auth_mode=MANUAL_ADAPTER_REQUIRED,
                execute=False,
                credential_ref=None,
                budget_gate_required=False,
                capability_proven=False,
                capability_proof_ref=None,
                reason="SUBSCRIPTION_OAUTH_PRESENT_CAPABILITY_UNVERIFIED",
            )
        return AuthDecision(
            auth_mode=SUBSCRIPTION,
            execute=True,
            credential_ref="CLAUDE_CODE_OAUTH_TOKEN",
            budget_gate_required=False,
            capability_proven=True,
            capability_proof_ref=capability_proof_ref,
            reason="SUBSCRIPTION_OAUTH_CAPABILITY_VERIFIED",
        )
    if api_key_present and allow_api_fallback:
        return AuthDecision(
            auth_mode=API_METERED,
            execute=True,
            credential_ref="ANTHROPIC_API_KEY",
            budget_gate_required=True,
            capability_proven=False,
            capability_proof_ref=None,
            reason="SUBSCRIPTION_UNAVAILABLE_API_FALLBACK",
        )
    if api_key_present:
        return AuthDecision(
            auth_mode=MANUAL_ADAPTER_REQUIRED,
            execute=False,
            credential_ref=None,
            budget_gate_required=False,
            capability_proven=False,
            capability_proof_ref=None,
            reason="SUBSCRIPTION_REQUIRED_API_FALLBACK_DISABLED",
        )
    return AuthDecision(
        auth_mode=MANUAL_ADAPTER_REQUIRED,
        execute=False,
        credential_ref=None,
        budget_gate_required=False,
        capability_proven=False,
        capability_proof_ref=None,
        reason="NO_SUPPORTED_CREDENTIAL_CONFIGURED",
    )


def resolve_auth_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    capability_receipt: Mapping[str, Any] | None = None,
    trusted_workflow_sha: str | None = None,
    allow_api_fallback: bool = True,
) -> AuthDecision:
    env = os.environ if environ is None else environ
    return resolve_auth(
        oauth_present=_present(env.get("CLAUDE_CODE_OAUTH_TOKEN")),
        api_key_present=_present(env.get("ANTHROPIC_API_KEY")),
        capability_receipt=capability_receipt,
        trusted_workflow_sha=trusted_workflow_sha,
        allow_api_fallback=allow_api_fallback,
    )


def validate_decision(payload: Mapping[str, Any]) -> None:
    mode = payload.get("auth_mode")
    if mode not in SAFE_AUTH_MODES:
        raise AuthPolicyError("unsupported auth mode")
    if not isinstance(payload.get("execute"), bool):
        raise AuthPolicyError("execute must be boolean")
    if not isinstance(payload.get("budget_gate_required"), bool):
        raise AuthPolicyError("budget_gate_required must be boolean")
    if not isinstance(payload.get("capability_proven"), bool):
        raise AuthPolicyError("capability_proven must be boolean")
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        raise AuthPolicyError("auth decision reason is required")

    ref = payload.get("credential_ref")
    if ref is not None and ref not in SECRET_ENV_NAMES:
        raise AuthPolicyError("credential reference is not an approved secret name")
    proof_ref = payload.get("capability_proof_ref")
    if proof_ref is not None and not _present(proof_ref):
        raise AuthPolicyError("capability proof reference must be non-empty")

    if mode == SUBSCRIPTION:
        if (
            payload.get("execute") is not True
            or ref != "CLAUDE_CODE_OAUTH_TOKEN"
            or payload.get("budget_gate_required")
            or payload.get("capability_proven") is not True
            or not _present(proof_ref)
        ):
            raise AuthPolicyError(
                "subscription auth must be proven, executable, non-metered OAuth with durable proof"
            )
    elif mode == API_METERED:
        if (
            payload.get("execute") is not True
            or ref != "ANTHROPIC_API_KEY"
            or not payload.get("budget_gate_required")
            or payload.get("capability_proven")
            or proof_ref is not None
        ):
            raise AuthPolicyError("API auth must be metered, budget-gated, and carry no subscription proof")
    else:
        if (
            payload.get("execute") is not False
            or ref is not None
            or payload.get("budget_gate_required")
            or payload.get("capability_proven")
            or proof_ref is not None
        ):
            raise AuthPolicyError(
                "non-executable auth modes cannot carry credentials, proof, or budget authority"
            )


def make_auth_receipt(
    *,
    task_id: str,
    request_id: str,
    branch: str,
    base_main_sha: str,
    decision: AuthDecision,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Create an immutable, secret-free receipt for one adapter attempt."""
    if not all(isinstance(v, str) and v.strip() for v in (task_id, request_id, branch, base_main_sha)):
        raise AuthPolicyError("receipt identity fields must be non-empty")
    _validate_branch_identity(branch)
    if not _valid_sha(base_main_sha):
        raise AuthPolicyError("base_main_sha must be a lowercase 40-character SHA")
    validate_decision(decision.as_dict())
    at = observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not _valid_time(at):
        raise AuthPolicyError("observed_at must be a timezone-aware ISO timestamp")
    identity = {
        "task_id": task_id,
        "request_id": request_id,
        "branch": branch,
        "base_main_sha": base_main_sha,
        "provider": "anthropic",
        "engine": "claude-code",
        "auth_mode": decision.auth_mode,
        "capability_proven": decision.capability_proven,
        "capability_proof_ref": decision.capability_proof_ref,
    }
    attempt_id = _digest(identity)
    body = {
        "version": 1,
        **identity,
        "attempt_id": attempt_id,
        "observed_at": at,
        "execute": decision.execute,
        "credential_ref": decision.credential_ref,
        "budget_gate_required": decision.budget_gate_required,
        "reason": decision.reason,
    }
    body["content_digest"] = _digest(body)
    validate_auth_receipt(body)
    return body


def validate_auth_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("version") != 1:
        raise AuthPolicyError("unsupported auth receipt version")
    if receipt.get("provider") != "anthropic" or receipt.get("engine") != "claude-code":
        raise AuthPolicyError("provider/engine mismatch")
    _validate_branch_identity(receipt.get("branch"))
    if not _valid_sha(receipt.get("base_main_sha")):
        raise AuthPolicyError("malformed base main SHA")
    for field in ("task_id", "request_id", "branch", "attempt_id", "reason", "content_digest"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            raise AuthPolicyError(f"missing receipt field: {field}")
    if not _valid_time(receipt.get("observed_at")):
        raise AuthPolicyError("malformed observed_at")
    decision = {
        "auth_mode": receipt.get("auth_mode"),
        "execute": receipt.get("execute"),
        "credential_ref": receipt.get("credential_ref"),
        "budget_gate_required": receipt.get("budget_gate_required"),
        "capability_proven": receipt.get("capability_proven"),
        "capability_proof_ref": receipt.get("capability_proof_ref"),
        "reason": receipt.get("reason"),
    }
    validate_decision(decision)
    identity = {
        "task_id": receipt["task_id"],
        "request_id": receipt["request_id"],
        "branch": receipt["branch"],
        "base_main_sha": receipt["base_main_sha"],
        "provider": receipt["provider"],
        "engine": receipt["engine"],
        "auth_mode": receipt["auth_mode"],
        "capability_proven": receipt["capability_proven"],
        "capability_proof_ref": receipt["capability_proof_ref"],
    }
    if receipt["attempt_id"] != _digest(identity):
        raise AuthPolicyError("attempt identity mismatch")
    unsigned = {k: v for k, v in receipt.items() if k != "content_digest"}
    if receipt["content_digest"] != _digest(unsigned):
        raise AuthPolicyError("auth receipt digest mismatch")
    raw = json.dumps(dict(receipt), sort_keys=True)
    for secret_name in SECRET_ENV_NAMES:
        secret_value = os.environ.get(secret_name)
        if secret_value and secret_value in raw:
            raise AuthPolicyError("credential value leaked into receipt")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--output", required=True)
    resolve.add_argument("--disable-api-fallback", action="store_true")
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--output", required=True)
    receipt.add_argument("--task-id", required=True)
    receipt.add_argument("--request-id", required=True)
    receipt.add_argument("--branch", required=True)
    receipt.add_argument("--base-main-sha", required=True)
    receipt.add_argument("--observed-at", default="")
    receipt.add_argument("--disable-api-fallback", action="store_true")
    args = parser.parse_args()

    # Standalone CLI intentionally cannot authorize subscription execution.
    # The trusted orchestration path must fetch a capability receipt from GitHub,
    # bind it to a separately trusted workflow/main SHA, and call the Python API.
    decision = resolve_auth_from_environment(
        capability_receipt=None,
        trusted_workflow_sha=None,
        allow_api_fallback=not args.disable_api_fallback,
    )
    if args.command == "resolve":
        payload = decision.as_dict()
    else:
        payload = make_auth_receipt(
            task_id=args.task_id,
            request_id=args.request_id,
            branch=args.branch,
            base_main_sha=args.base_main_sha,
            decision=decision,
            observed_at=args.observed_at or None,
        )
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

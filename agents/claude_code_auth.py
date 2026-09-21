from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SUBSCRIPTION = "SUBSCRIPTION"
API_METERED = "API_METERED"
MANUAL_ADAPTER_REQUIRED = "MANUAL_ADAPTER_REQUIRED"
UNKNOWN = "UNKNOWN"

SAFE_AUTH_MODES = {SUBSCRIPTION, API_METERED, MANUAL_ADAPTER_REQUIRED, UNKNOWN}
SECRET_ENV_NAMES = {"CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"}


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


@dataclass(frozen=True)
class AuthDecision:
    auth_mode: str
    execute: bool
    credential_ref: str | None
    budget_gate_required: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        validate_decision(result)
        return result


def resolve_auth(
    *,
    oauth_present: bool,
    api_key_present: bool,
    allow_api_fallback: bool = True,
) -> AuthDecision:
    """Select authentication without accepting or returning any credential value."""
    if oauth_present:
        return AuthDecision(
            auth_mode=SUBSCRIPTION,
            execute=True,
            credential_ref="CLAUDE_CODE_OAUTH_TOKEN",
            budget_gate_required=False,
            reason="SUBSCRIPTION_OAUTH_PREFERRED",
        )
    if api_key_present and allow_api_fallback:
        return AuthDecision(
            auth_mode=API_METERED,
            execute=True,
            credential_ref="ANTHROPIC_API_KEY",
            budget_gate_required=True,
            reason="SUBSCRIPTION_UNAVAILABLE_API_FALLBACK",
        )
    if api_key_present:
        return AuthDecision(
            auth_mode=MANUAL_ADAPTER_REQUIRED,
            execute=False,
            credential_ref=None,
            budget_gate_required=False,
            reason="SUBSCRIPTION_REQUIRED_API_FALLBACK_DISABLED",
        )
    return AuthDecision(
        auth_mode=MANUAL_ADAPTER_REQUIRED,
        execute=False,
        credential_ref=None,
        budget_gate_required=False,
        reason="NO_SUPPORTED_CREDENTIAL_CONFIGURED",
    )


def resolve_auth_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    allow_api_fallback: bool = True,
) -> AuthDecision:
    env = os.environ if environ is None else environ
    return resolve_auth(
        oauth_present=_present(env.get("CLAUDE_CODE_OAUTH_TOKEN")),
        api_key_present=_present(env.get("ANTHROPIC_API_KEY")),
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
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        raise AuthPolicyError("auth decision reason is required")
    ref = payload.get("credential_ref")
    if ref is not None and ref not in SECRET_ENV_NAMES:
        raise AuthPolicyError("credential reference is not an approved secret name")
    if mode == SUBSCRIPTION:
        if payload.get("execute") is not True or ref != "CLAUDE_CODE_OAUTH_TOKEN" or payload.get("budget_gate_required"):
            raise AuthPolicyError("subscription auth must be executable non-metered OAuth")
    elif mode == API_METERED:
        if payload.get("execute") is not True or ref != "ANTHROPIC_API_KEY" or not payload.get("budget_gate_required"):
            raise AuthPolicyError("API auth must be executable and retain the budget gate")
    else:
        if payload.get("execute") is not False or ref is not None or payload.get("budget_gate_required"):
            raise AuthPolicyError("non-executable auth modes cannot carry credentials or budget authority")


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
    if branch in {"main", "master"}:
        raise AuthPolicyError("adapter attempt cannot target main")
    if len(base_main_sha) != 40 or any(c not in "0123456789abcdef" for c in base_main_sha):
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
    if receipt.get("branch") in {"main", "master"}:
        raise AuthPolicyError("receipt cannot target main")
    sha = receipt.get("base_main_sha")
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
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

    decision = resolve_auth_from_environment(
        allow_api_fallback=not args.disable_api_fallback
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

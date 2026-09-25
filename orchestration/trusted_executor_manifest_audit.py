"""Machine-verifiable audit receipts for trusted research-executor changes."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from profitability_learning import contracts


RECEIPT_PATH = Path(__file__).with_name("trusted_executor_manifest_receipts.jsonl")
_RECEIPT_FIELDS = {
    "schema_version",
    "execution_rule",
    "base_commit_sha",
    "base_manifest_sha256",
    "previous_bundle_sha256",
    "bundle_sha256",
    "bundle_change_paths",
    "behavior_change_files",
    "change_reason",
}


def _sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")
    return value


def _commit_sha(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("base commit must be a lowercase Git SHA")
    return value


def _behavior_files(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError("trusted executor receipt requires behavior file digests")
    validated: dict[str, str] = {}
    for path, digest in value.items():
        if (
            not isinstance(path, str)
            or not path.endswith(".py")
            or Path(path).is_absolute()
            or ".." in Path(path).parts
        ):
            raise ValueError("invalid trusted executor behavior path")
        validated[path] = _sha256(digest, "behavior file")
    return validated


def _load_receipts() -> list[dict[str, Any]]:
    try:
        lines = RECEIPT_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("trusted executor manifest receipts are unreadable") from exc
    if not lines or any(not line.strip() for line in lines):
        raise ValueError("trusted executor manifest receipts must be nonempty JSONL")

    receipts: list[dict[str, Any]] = []
    last_digest_by_rule: dict[str, str] = {}
    for line in lines:
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("trusted executor manifest receipt is invalid JSON") from exc
        if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
            raise ValueError("invalid trusted executor manifest receipt schema")
        if receipt["schema_version"] != 2:
            raise ValueError("unknown trusted executor manifest receipt schema")
        rule = receipt["execution_rule"]
        if not isinstance(rule, str) or not rule:
            raise ValueError("trusted executor receipt requires an execution rule")
        previous = _sha256(receipt["previous_bundle_sha256"], "previous bundle")
        current = _sha256(receipt["bundle_sha256"], "bundle")
        if previous == current:
            raise ValueError("trusted executor receipt must record a changed bundle")
        if rule in last_digest_by_rule and previous != last_digest_by_rule[rule]:
            raise ValueError("trusted executor receipt chain is broken")
        _commit_sha(receipt["base_commit_sha"])
        _sha256(receipt["base_manifest_sha256"], "base manifest")
        paths = receipt["bundle_change_paths"]
        if (
            not isinstance(paths, list)
            or not paths
            or len(paths) != len(set(paths))
            or any(not isinstance(path, str) or not path for path in paths)
        ):
            raise ValueError("trusted executor receipt requires distinct bundle paths")
        behavior_files = _behavior_files(receipt["behavior_change_files"])
        if any(path not in behavior_files for path in paths):
            raise ValueError("bundle change paths must be behavior-file bound")
        reason = receipt["change_reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
            raise ValueError("trusted executor receipt requires a bounded change reason")
        last_digest_by_rule[rule] = current
        receipts.append(receipt)
    return receipts


def audit_executor_manifest(execution_rule: str) -> dict[str, Any]:
    """Prove the registry digest, actual bundle, and latest receipt agree."""
    registered = contracts.trusted_executor_implementation(execution_rule)
    computed = contracts._executor_bundle_digest(execution_rule)
    source = contracts._registered_executor_source(execution_rule)
    root = Path(contracts.__file__).resolve().parent.parent
    dependencies = sorted(
        contracts._executor_python_closure(root, source["entrypoint"])
    )
    matching = [
        receipt
        for receipt in _load_receipts()
        if receipt["execution_rule"] == execution_rule
    ]
    if not matching:
        raise ValueError("trusted executor has no manifest audit receipt")
    latest = matching[-1]
    if latest["bundle_sha256"] != registered["ast_sha256"]:
        raise ValueError("trusted executor receipt does not match registered digest")
    if computed != registered["ast_sha256"]:
        raise ValueError("trusted executor registered digest is stale")
    if any(path not in dependencies for path in latest["bundle_change_paths"]):
        raise ValueError("trusted executor receipt names an unbound behavior path")
    for relative_path, expected_digest in latest["behavior_change_files"].items():
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("trusted executor behavior file is unavailable")
        if sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise ValueError("trusted executor behavior file digest is stale")

    return {
        "schema_version": 2,
        "execution_rule": execution_rule,
        "implementation_id": registered["implementation_id"],
        "previous_bundle_sha256": latest["previous_bundle_sha256"],
        "registered_bundle_sha256": registered["ast_sha256"],
        "computed_bundle_sha256": computed,
        "base_commit_sha": latest["base_commit_sha"],
        "base_manifest_sha256": latest["base_manifest_sha256"],
        "bundle_change_paths": list(latest["bundle_change_paths"]),
        "behavior_change_files": dict(latest["behavior_change_files"]),
        "change_reason": latest["change_reason"],
        "dependency_paths": dependencies,
        "resource_paths": list(source["resources"]),
    }

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlsplit

EXPECTED_REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
EXPECTED_OWNER = "rnnyrgs-web"
TARGET_WORKFLOW = "pit-trusted-remote-acquisition.yml"
TARGET_REF = "main"
TITLE_PREFIX = "pit-trusted-acquisition-request: "
COLLECTION_RE = re.compile(r"^CC-MAIN-[0-9]{4}-[0-9]{2}$")
WARC_RE = re.compile(r"^crawl-data/(CC-MAIN-[0-9]{4}-[0-9]{2})/.+\.warc\.gz$")
MAX_RANGE_BYTES = 16 * 1024 * 1024
DISPATCH_MARKER = "PIT_TRUSTED_ACQUISITION_DISPATCHED"
TRUSTED_MARKER_AUTHORS = {"github-actions", "github-actions[bot]"}


class BridgeRequestError(ValueError):
    pass


def _require_dict(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BridgeRequestError(f"{name} must be an object")
    return value


def _require_exact_keys(payload: dict[str, Any], expected: set[str]) -> None:
    if set(payload) != expected:
        raise BridgeRequestError(
            f"request body keys must be exactly {sorted(expected)}"
        )


def _require_collection(value: Any) -> str:
    if not isinstance(value, str) or not COLLECTION_RE.fullmatch(value):
        raise BridgeRequestError("invalid Common Crawl collection")
    return value


def _require_https_url(value: Any) -> str:
    if not isinstance(value, str) or not value or any(ch in value for ch in "\r\n\x00"):
        raise BridgeRequestError("target_url must be one clean HTTPS URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise BridgeRequestError("target_url must be one clean HTTPS URL")
    return value


def _require_decimal_int(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise BridgeRequestError(f"{name} must be a decimal integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        number = int(value)
    else:
        raise BridgeRequestError(f"{name} must be a decimal integer")
    if not minimum <= number <= maximum:
        raise BridgeRequestError(f"{name} out of bounds")
    return number


def validate_event(event: dict[str, Any]) -> tuple[int, str, dict[str, str]]:
    repository = _require_dict(event.get("repository"), name="repository")
    issue = _require_dict(event.get("issue"), name="issue")
    sender = _require_dict(event.get("sender"), name="sender")
    issue_user = _require_dict(issue.get("user"), name="issue.user")
    repository_owner = _require_dict(repository.get("owner"), name="repository.owner")

    if repository.get("full_name") != EXPECTED_REPOSITORY:
        raise BridgeRequestError("request came from the wrong repository")
    if repository.get("default_branch") != TARGET_REF:
        raise BridgeRequestError("repository default branch is not trusted main")
    if repository_owner.get("login") != EXPECTED_OWNER:
        raise BridgeRequestError("repository owner mismatch")
    if event.get("action") != "opened":
        raise BridgeRequestError("only newly opened request issues are accepted")
    if issue.get("state") != "open":
        raise BridgeRequestError("request issue must be open")
    if issue_user.get("login") != EXPECTED_OWNER or sender.get("login") != EXPECTED_OWNER:
        raise BridgeRequestError("only the repository owner may authorize acquisition")

    issue_number = issue.get("number")
    if not isinstance(issue_number, int) or issue_number <= 0:
        raise BridgeRequestError("invalid issue number")

    title = issue.get("title")
    if not isinstance(title, str) or not title.startswith(TITLE_PREFIX):
        raise BridgeRequestError("request issue title does not match the frozen bridge format")
    source_kind = title[len(TITLE_PREFIX) :]
    if source_kind not in {"COMMONCRAWL_INDEX", "COMMONCRAWL_WARC_RANGE"}:
        raise BridgeRequestError("unsupported acquisition request kind")

    body = issue.get("body")
    if not isinstance(body, str):
        raise BridgeRequestError("request issue body must contain strict JSON")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BridgeRequestError("request issue body must contain strict JSON") from exc
    payload = _require_dict(payload, name="request body")

    if source_kind == "COMMONCRAWL_INDEX":
        _require_exact_keys(payload, {"collection", "target_url"})
        fields = {
            "source_kind": source_kind,
            "collection": _require_collection(payload["collection"]),
            "target_url": _require_https_url(payload["target_url"]),
        }
    else:
        _require_exact_keys(payload, {"collection", "filename", "offset", "length"})
        collection = _require_collection(payload["collection"])
        filename = payload["filename"]
        if not isinstance(filename, str) or any(ch in filename for ch in "\r\n\x00"):
            raise BridgeRequestError("invalid Common Crawl WARC filename")
        match = WARC_RE.fullmatch(filename)
        if not match or match.group(1) != collection or ".." in filename:
            raise BridgeRequestError("WARC filename must be bound to the requested collection")
        offset = _require_decimal_int(
            payload["offset"], name="offset", minimum=0, maximum=10**15
        )
        length = _require_decimal_int(
            payload["length"], name="length", minimum=1, maximum=MAX_RANGE_BYTES
        )
        fields = {
            "source_kind": source_kind,
            "collection": collection,
            "filename": filename,
            "offset": str(offset),
            "length": str(length),
        }

    return issue_number, source_kind, fields


def build_dispatch_argv(fields: dict[str, str]) -> list[str]:
    argv = [
        "gh",
        "workflow",
        "run",
        TARGET_WORKFLOW,
        "--repo",
        EXPECTED_REPOSITORY,
        "--ref",
        TARGET_REF,
    ]
    for name in ("source_kind", "collection", "target_url", "filename", "offset", "length"):
        value = fields.get(name)
        if value is not None:
            argv.extend(["-f", f"{name}={value}"])
    return argv


def _issue_has_dispatch_marker(issue_number: int, env: dict[str, str]) -> bool:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo",
            EXPECTED_REPOSITORY,
            "--json",
            "state,comments",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    data = json.loads(result.stdout)
    if data.get("state") != "OPEN":
        return True
    for comment in data.get("comments", []):
        author = (comment.get("author") or {}).get("login")
        body = comment.get("body") or ""
        if author in TRUSTED_MARKER_AUTHORS and DISPATCH_MARKER in body:
            return True
    return False


def dispatch(event: dict[str, Any], *, env: dict[str, str] | None = None) -> list[str]:
    issue_number, source_kind, fields = validate_event(event)
    runtime_env = dict(os.environ if env is None else env)
    if not runtime_env.get("GH_TOKEN"):
        raise BridgeRequestError("GH_TOKEN is required for trusted bridge dispatch")
    if _issue_has_dispatch_marker(issue_number, runtime_env):
        return []

    argv = build_dispatch_argv(fields)
    subprocess.run(argv, check=True, env=runtime_env)

    marker = (
        f"{DISPATCH_MARKER} issue={issue_number} kind={source_kind} "
        f"target_workflow={TARGET_WORKFLOW} ref={TARGET_REF}. "
        "The bridge grants no data/label/prediction authority; trust still comes from the "
        "canonical workflow_dispatch acquisition receipt + GitHub attestation."
    )
    subprocess.run(
        [
            "gh",
            "issue",
            "comment",
            str(issue_number),
            "--repo",
            EXPECTED_REPOSITORY,
            "--body",
            marker,
        ],
        check=True,
        env=runtime_env,
    )
    subprocess.run(
        [
            "gh",
            "issue",
            "close",
            str(issue_number),
            "--repo",
            EXPECTED_REPOSITORY,
            "--reason",
            "completed",
        ],
        check=True,
        env=runtime_env,
    )
    return argv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    event = json.loads(args.event.read_text(encoding="utf-8"))
    issue_number, source_kind, fields = validate_event(event)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "issue_number": issue_number,
                    "source_kind": source_kind,
                    "dispatch_argv": build_dispatch_argv(fields),
                },
                sort_keys=True,
            )
        )
        return
    dispatch(event)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import re
import ssl
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
GITHUB_API_HOST = "api.github.com"
GITHUB_API_VERSION = "2022-11-28"
MAX_API_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_COMMENT_PAGES = 100


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


def build_dispatch_payload(fields: dict[str, str]) -> dict[str, Any]:
    allowed = {"source_kind", "collection", "target_url", "filename", "offset", "length"}
    if not fields or set(fields) - allowed:
        raise BridgeRequestError("dispatch fields escaped the frozen bridge allowlist")
    return {"ref": TARGET_REF, "inputs": dict(fields)}


def _github_json_request(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    expected_status: set[int],
) -> Any:
    repo_prefix = f"/repos/{EXPECTED_REPOSITORY}/"
    if method not in {"GET", "POST", "PATCH"} or not path.startswith(repo_prefix):
        raise BridgeRequestError("GitHub API request escaped frozen repository boundary")
    if "\r" in path or "\n" in path or "\x00" in path:
        raise BridgeRequestError("invalid GitHub API path")

    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "rnnyrgs-pit-acquisition-issue-bridge/1",
        "Connection": "close",
    }
    if payload is not None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = http.client.HTTPSConnection(
        GITHUB_API_HOST,
        443,
        timeout=20,
        context=ssl.create_default_context(),
    )
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_API_RESPONSE_BYTES + 1)
        status = int(response.status)
    finally:
        connection.close()

    if len(raw) > MAX_API_RESPONSE_BYTES:
        raise BridgeRequestError("GitHub API response exceeded frozen bridge bound")
    if status not in expected_status:
        raise BridgeRequestError(f"GitHub API request failed with HTTP {status}")
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeRequestError("GitHub API returned malformed JSON") from exc


def _issue_is_already_dispatched(issue_number: int, token: str) -> bool:
    issue_path = f"/repos/{EXPECTED_REPOSITORY}/issues/{issue_number}"
    issue = _require_dict(
        _github_json_request(
            "GET", issue_path, token=token, expected_status={200}
        ),
        name="GitHub issue",
    )
    if issue.get("state") != "open":
        return True

    for page in range(1, MAX_COMMENT_PAGES + 1):
        comments = _github_json_request(
            "GET",
            f"{issue_path}/comments?per_page=100&page={page}",
            token=token,
            expected_status={200},
        )
        if not isinstance(comments, list):
            raise BridgeRequestError("GitHub issue comments response must be a list")
        for comment in comments:
            if not isinstance(comment, dict):
                raise BridgeRequestError("GitHub issue comment must be an object")
            author = (comment.get("user") or {}).get("login")
            body = comment.get("body") or ""
            if author in TRUSTED_MARKER_AUTHORS and DISPATCH_MARKER in body:
                return True
        if len(comments) < 100:
            return False
    raise BridgeRequestError("too many issue comments to prove bridge idempotency")


def dispatch(
    event: dict[str, Any], *, token: str | None = None
) -> dict[str, Any] | None:
    issue_number, source_kind, fields = validate_event(event)
    runtime_token = token if token is not None else os.environ.get("GH_TOKEN")
    if not runtime_token:
        raise BridgeRequestError("GH_TOKEN is required for trusted bridge dispatch")
    if _issue_is_already_dispatched(issue_number, runtime_token):
        return None

    dispatch_payload = build_dispatch_payload(fields)
    _github_json_request(
        "POST",
        f"/repos/{EXPECTED_REPOSITORY}/actions/workflows/{TARGET_WORKFLOW}/dispatches",
        token=runtime_token,
        payload=dispatch_payload,
        expected_status={204},
    )

    marker = (
        f"{DISPATCH_MARKER} issue={issue_number} kind={source_kind} "
        f"target_workflow={TARGET_WORKFLOW} ref={TARGET_REF}. "
        "The bridge grants no data/label/prediction authority; trust still comes from the "
        "canonical workflow_dispatch acquisition receipt + GitHub attestation."
    )
    issue_path = f"/repos/{EXPECTED_REPOSITORY}/issues/{issue_number}"
    _github_json_request(
        "POST",
        f"{issue_path}/comments",
        token=runtime_token,
        payload={"body": marker},
        expected_status={201},
    )
    _github_json_request(
        "PATCH",
        issue_path,
        token=runtime_token,
        payload={"state": "closed", "state_reason": "completed"},
        expected_status={200},
    )
    return dispatch_payload


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
                    "dispatch_payload": build_dispatch_payload(fields),
                },
                sort_keys=True,
            )
        )
        return
    dispatch(event)


if __name__ == "__main__":
    main()

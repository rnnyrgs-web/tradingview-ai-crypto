import os
from urllib.parse import quote

import httpx


class SentryConfigurationError(RuntimeError):
    pass


class SentryAPIError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _base_config():
    token = os.getenv("SENTRY_AUTH_TOKEN", "").strip()
    base_url = os.getenv("SENTRY_BASE_URL", "https://sentry.io").strip().rstrip("/")
    if not token:
        raise SentryConfigurationError("Sentry read-only observability is not configured")
    if not base_url.startswith("https://"):
        raise SentryConfigurationError("SENTRY_BASE_URL must use HTTPS")
    return token, base_url


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "tradingview-ai-crypto/sentry-observability",
    }


def _get_json(url, token, params=None):
    try:
        response = httpx.get(
            url,
            params=params,
            headers=_headers(token),
            timeout=10.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise SentryAPIError("Sentry API request failed", status_code=exc.response.status_code) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SentryAPIError("Sentry API request failed") from exc


def _target():
    token, base_url = _base_config()
    org = os.getenv("SENTRY_ORG", "").strip()
    project = os.getenv("SENTRY_PROJECT", "").strip()

    if not org:
        organizations = _get_json(f"{base_url}/api/0/organizations/", token)
        if not isinstance(organizations, list) or len(organizations) != 1:
            raise SentryConfigurationError("Set SENTRY_ORG when the token can access multiple organizations")
        org = str(organizations[0].get("slug") or "").strip()
        if not org:
            raise SentryConfigurationError("Unable to discover Sentry organization slug")

    if not project:
        projects = _get_json(
            f"{base_url}/api/0/organizations/{quote(org, safe='')}/projects/",
            token,
            params={"per_page": 100},
        )
        if not isinstance(projects, list):
            raise SentryAPIError("Unexpected Sentry projects response")
        candidates = [str(item.get("slug") or "").strip() for item in projects if isinstance(item, dict)]
        candidates = [slug for slug in candidates if slug]
        if "tradingview-ai-crypto" in candidates:
            project = "tradingview-ai-crypto"
        elif len(candidates) == 1:
            project = candidates[0]
        else:
            raise SentryConfigurationError("Set SENTRY_PROJECT when the organization has multiple projects")

    return token, org, project, base_url


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def sanitize_issues(items):
    safe = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        safe.append({
            "id": str(item.get("id") or ""),
            "short_id": str(item.get("shortId") or ""),
            "title": str(item.get("title") or "")[:500],
            "count": _safe_int(item.get("count")),
            "user_count": _safe_int(item.get("userCount")),
            "last_seen": str(item.get("lastSeen") or ""),
            "permalink": str(item.get("permalink") or ""),
            "culprit": str(item.get("culprit") or "")[:500],
        })
    return safe


def fetch_recent_issues(limit=20, stats_period="24h", environment="production"):
    token, org, project, base_url = _target()
    limit = max(1, min(int(limit), 50))
    params = {
        "project": project,
        "query": "is:unresolved",
        "sort": "freq",
        "limit": limit,
        "statsPeriod": stats_period,
    }
    if environment:
        params["environment"] = environment
    payload = _get_json(
        f"{base_url}/api/0/organizations/{quote(org, safe='')}/issues/",
        token,
        params=params,
    )
    if not isinstance(payload, list):
        raise SentryAPIError("Unexpected Sentry API response")
    return sanitize_issues(payload)


def snapshot(limit=20):
    issues = fetch_recent_issues(limit=limit)
    return {
        "configured": True,
        "read_only": True,
        "window": "24h",
        "environment": "production",
        "issue_count": len(issues),
        "issues": issues,
    }

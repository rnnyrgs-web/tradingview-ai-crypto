import os
from urllib.parse import quote

import httpx


class SentryConfigurationError(RuntimeError):
    pass


class SentryAPIError(RuntimeError):
    pass


def _config():
    token = os.getenv("SENTRY_AUTH_TOKEN", "").strip()
    org = os.getenv("SENTRY_ORG", "").strip()
    project = os.getenv("SENTRY_PROJECT", "").strip()
    base_url = os.getenv("SENTRY_BASE_URL", "https://sentry.io").strip().rstrip("/")
    if not token or not org or not project:
        raise SentryConfigurationError("Sentry read-only observability is not configured")
    if not base_url.startswith("https://"):
        raise SentryConfigurationError("SENTRY_BASE_URL must use HTTPS")
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
    token, org, project, base_url = _config()
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
    url = f"{base_url}/api/0/organizations/{quote(org, safe='')}/issues/"
    try:
        response = httpx.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "tradingview-ai-crypto/sentry-observability",
            },
            timeout=10.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SentryAPIError("Sentry API request failed") from exc
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

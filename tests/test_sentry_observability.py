import importlib

import pytest


def test_sentry_observability_requires_configuration(monkeypatch):
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)

    import sentry_observability
    importlib.reload(sentry_observability)

    with pytest.raises(sentry_observability.SentryConfigurationError):
        sentry_observability.fetch_recent_issues()


def test_sentry_observability_redacts_sensitive_fields(monkeypatch):
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("SENTRY_ORG", "example-org")
    monkeypatch.setenv("SENTRY_PROJECT", "example-project")

    import sentry_observability
    importlib.reload(sentry_observability)

    payload = [{
        "id": "123",
        "shortId": "APP-1",
        "title": "ValueError",
        "count": "7",
        "userCount": 2,
        "lastSeen": "2026-09-16T12:00:00Z",
        "permalink": "https://example.sentry.io/issues/123/",
        "culprit": "worker.loop",
        "metadata": {"token": "must-not-leak"},
    }]

    result = sentry_observability.sanitize_issues(payload)

    assert result == [{
        "id": "123",
        "short_id": "APP-1",
        "title": "ValueError",
        "count": 7,
        "user_count": 2,
        "last_seen": "2026-09-16T12:00:00Z",
        "permalink": "https://example.sentry.io/issues/123/",
        "culprit": "worker.loop",
    }]
    assert "secret-token" not in repr(result)
    assert "must-not-leak" not in repr(result)

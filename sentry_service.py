import hashlib
import hmac
import logging
import os
import time

from fastapi import HTTPException

from app import app, internal_error
from sentry_observability import snapshot as sentry_snapshot

log = logging.getLogger(__name__)


def _verify_observability_signature(ts: int, sig: str):
    secret = os.getenv("SENTRY_OBSERVABILITY_SECRET", "").strip()
    if not secret or not sig:
        raise HTTPException(status_code=401, detail="Unauthorized")
    now = int(time.time())
    if abs(now - int(ts)) > 90:
        raise HTTPException(status_code=401, detail="Expired")
    message = f"sentry-observability:{int(ts)}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _verify_sentry_connection_at_startup():
    try:
        result = sentry_snapshot(limit=1)
        log.warning(
            "SENTRY_OBSERVABILITY_CONNECTED read_only=true issue_count=%s",
            result.get("issue_count", 0),
        )
    except Exception as exc:
        log.error("SENTRY_OBSERVABILITY_CONNECTION_FAILED type=%s", type(exc).__name__)


_verify_sentry_connection_at_startup()


@app.get("/sentry-observability")
def sentry_observability(ts: int, sig: str):
    _verify_observability_signature(ts, sig)
    try:
        return {"ok": True, **sentry_snapshot()}
    except Exception as exc:
        internal_error("sentry_observability", exc, "Sentry observability unavailable")

from typing import Optional

from fastapi import Header

from app import app, internal_error, verify_secret
from sentry_observability import snapshot as sentry_snapshot


@app.get("/sentry-observability")
def sentry_observability(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return {"ok": True, **sentry_snapshot()}
    except Exception as exc:
        internal_error("sentry_observability", exc, "Sentry observability unavailable")

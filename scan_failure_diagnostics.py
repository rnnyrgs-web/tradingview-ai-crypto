"""Privacy-preserving diagnostics for production scan failures.

Never returns raw exception messages because upstream/database responses may
contain sensitive details. The fingerprint is deterministic enough to group
recurring failures while keeping production fail-closed.
"""

from __future__ import annotations

import hashlib


def safe_failure(component: str, exc: BaseException) -> dict:
    exc_type = type(exc).__name__
    fingerprint = hashlib.sha256(f"{component}:{exc_type}".encode("utf-8")).hexdigest()[:16]
    return {
        "component": component,
        "exception_type": exc_type,
        "fingerprint": fingerprint,
        "detail_redacted": True,
        "trade_authority": False,
        "promotion_authority": False,
    }

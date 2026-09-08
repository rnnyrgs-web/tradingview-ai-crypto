from scan_failure_diagnostics import safe_failure


def test_safe_failure_redacts_exception_message_and_is_stable():
    secret = "Bearer super-secret-token"
    first = safe_failure("opportunity_persistence", RuntimeError(secret))
    second = safe_failure("opportunity_persistence", RuntimeError("different sensitive detail"))
    assert secret not in str(first)
    assert first["exception_type"] == "RuntimeError"
    assert first["fingerprint"] == second["fingerprint"]
    assert first["detail_redacted"] is True
    assert first["trade_authority"] is False
    assert first["promotion_authority"] is False


def test_different_failure_types_get_different_fingerprints():
    a = safe_failure("opportunity_persistence", RuntimeError("x"))
    b = safe_failure("opportunity_persistence", ValueError("x"))
    assert a["fingerprint"] != b["fingerprint"]

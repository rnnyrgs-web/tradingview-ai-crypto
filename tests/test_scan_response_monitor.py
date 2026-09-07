import pytest

from tools.validate_scan_response import validate_scan_payload


def _healthy_payload():
    return {
        "ok": True,
        "universe_count": 80,
        "deep_scanned": 40,
        "scan_error_count": 0,
        "ai_error": None,
        "opportunity_error": None,
        "signals": [{
            "symbol": "ETH-USDT",
            "action": "WAIT",
            "raw_analysis": {"research_validation": {
                "approved": False,
                "strategy_identity": {"fingerprint": "a" * 64},
            }},
        }],
    }


def test_healthy_fail_closed_scan_passes_monitor():
    assert validate_scan_payload(_healthy_payload()) == []


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("ok", False, "scan did not report ok=true"),
        ("universe_count", 0, "empty market universe"),
        ("deep_scanned", 0, "no markets completed deep scan"),
        ("ai_error", "timeout", "AI review failed"),
        ("opportunity_error", "database unavailable", "opportunity persistence failed"),
    ],
)
def test_scan_response_failures_are_rejected(field, value, expected_error):
    payload = _healthy_payload()
    payload[field] = value

    assert expected_error in validate_scan_payload(payload)


def test_unvalidated_trade_fails_monitor():
    payload = _healthy_payload()
    payload["signals"][0]["action"] = "TRADE"
    errors = validate_scan_payload(payload)
    assert any("unvalidated TRADE escaped gate" in error for error in errors)


def test_missing_identity_fails_monitor():
    payload = _healthy_payload()
    payload["signals"][0]["raw_analysis"]["research_validation"].pop("strategy_identity")
    assert validate_scan_payload(payload) == ["missing strategy fingerprint: ETH-USDT"]


def test_excessive_symbol_failure_rate_fails_monitor():
    payload = _healthy_payload()
    payload["deep_scanned"] = 30
    payload["scan_error_count"] = 10
    assert validate_scan_payload(payload) == ["more than 20% of deep-scan candidates failed"]

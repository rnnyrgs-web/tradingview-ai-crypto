import pytest

import operational_monitor as monitor
import opportunity_engine as opportunities
import production_validation as validation
import strategy_identity
from agents.autonomous_orchestrator import path_allowed, write_file


def test_malformed_research_identity_fails_research_only(monkeypatch):
    monkeypatch.setattr(validation, "LIVE_VALIDATED_STRATEGIES", frozenset())

    malformed = [
        (None, "24h", "trend"),
        ("ETH-USDT", None, "trend"),
        ("ETH-USDT", "24h\x00", "trend"),
        ({"symbol": "ETH-USDT"}, "24h", "trend"),
        ("ETH-USDT", "24h", ["trend"]),
    ]
    for symbol, horizon, family in malformed:
        decision = validation.validate_live_strategy(symbol, horizon, family)
        assert decision.approved is False
        assert decision.status == "RESEARCH_ONLY"


def test_stale_registered_fingerprint_is_invalid_after_research_code_changes(monkeypatch):
    old_identity = validation.build_strategy_identity("ETH-USDT", "24h", "trend")
    monkeypatch.setattr(
        validation,
        "LIVE_VALIDATED_STRATEGIES",
        frozenset({old_identity["fingerprint"]}),
    )
    monkeypatch.setattr(strategy_identity, "research_code_sha256", lambda: "f" * 64)

    decision = validation.validate_live_strategy("ETH-USDT", "24h", "trend")

    assert decision.identity["research_code_sha256"] == "f" * 64
    assert decision.identity["fingerprint"] != old_identity["fingerprint"]
    assert decision.approved is False
    assert decision.status == "RESEARCH_ONLY"


@pytest.mark.parametrize("unauthorized_action", ["BUY", "SELL", "EXECUTE"])
def test_non_trade_action_cannot_bypass_opportunity_gate(monkeypatch, unauthorized_action):
    monkeypatch.setattr(opportunities, "replace_opportunities", lambda *args: None)
    monkeypatch.setattr(
        opportunities,
        "validate_live_strategy",
        lambda *args: type(
            "Decision",
            (),
            {
                "approved": True,
                "status": "LIVE_VALIDATED",
                "reason": "approved",
                "identity": {"fingerprint": "a" * 64},
            },
        )(),
    )
    candidates = [{
        "symbol": "ETH-USDT",
        "activity_score": 1.0,
        "spread_bps": 1.0,
        "horizons": {"24h": {"score": 1.0, "features": {"1H": {"last": 100.0}}}},
    }]
    ai_signals = [{
        "symbol": "ETH-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "strategy_family": "trend",
        "action": unauthorized_action,
        "evidence_score": 99,
    }]

    result = opportunities.build_opportunities(
        "scan",
        candidates,
        ai_signals,
        "BULL_TREND",
        lambda *args: {"entry": 100.0, "stop": 90.0, "t1": 119.0, "t2": 130.0, "rr": 1.9},
    )

    assert result["24h"][0]["action"] == "WAIT"


@pytest.mark.parametrize(
    "protected_path",
    [
        "AI_STATE.md",
        "./AI_STATE.md",
        "agents/roles.json",
        "agents/nested/config.json",
        ".github/workflows/security.yml",
        ".github/workflows/nested/security.yml",
        "requirements.txt",
        "Dockerfile",
        "tests/../AI_STATE.md",
    ],
)
def test_testing_security_cannot_write_protected_path_variants(protected_path):
    assert path_allowed("testing-security", protected_path) is False
    assert write_file("testing-security", protected_path, "adversarial overwrite") == (
        "ERROR: path is not writable for this role"
    )


def test_health_snapshot_does_not_leak_exception_or_untrusted_scan_fields():
    secret = "sk-adversarial-secret-sentinel"
    monitor.record_error("scan", RuntimeError(f"Authorization: Bearer {secret}"))
    monitor.record_scan({
        "scan_id": "sanitized-scan",
        "ok": False,
        "ai_error": f"upstream body contained {secret}",
        "opportunity_error": f"database password={secret}",
        "scan_errors": [{"error": secret}],
        "raw_response": {"api_key": secret},
    })

    snapshot = monitor.health_snapshot()

    assert secret not in str(snapshot)
    assert snapshot["last_scan"]["ai_ok"] is False
    assert snapshot["last_scan"]["opportunities_ok"] is False

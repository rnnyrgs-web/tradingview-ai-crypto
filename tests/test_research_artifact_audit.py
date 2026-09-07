from research_artifact import seal_research_payload
from research_artifact_audit import audit_envelope


def valid_payload(strategy=None, execution=None):
    item = {"ok": True, "symbol": "BTC-USDT", "bar": "15m"}
    if strategy is not None:
        item["strategy_registry"] = {"registry": [strategy]}
    if execution is not None:
        item["execution_oos_robustness"] = execution
    return seal_research_payload({"results": [item]})


def test_audit_accepts_research_only_execution_and_gated_strategy():
    envelope = valid_payload(
        strategy={
            "status": "ROBUST_OOS",
            "quality_gate": {"passed": True},
            "robustness": {"passed": True},
            "eligible_for_promotion_review": True,
        },
        execution={
            "research_only": True,
            "historical_slippage_available": False,
            "same_trade_path_policy": True,
            "current_snapshot_anchor": {"available": True, "historical": False},
        },
    )
    report = audit_envelope(envelope)
    assert report["ok"] is True
    assert report["failures"] == []


def test_audit_rejects_historical_misrepresentation():
    envelope = valid_payload(
        execution={
            "research_only": True,
            "historical_slippage_available": False,
            "same_trade_path_policy": True,
            "current_snapshot_anchor": {"available": True, "historical": True},
        }
    )
    report = audit_envelope(envelope)
    assert report["ok"] is False
    assert any("misrepresented_as_historical" in reason for reason in report["failures"])


def test_audit_rejects_promotion_bypass():
    envelope = valid_payload(
        strategy={
            "status": "ROBUST_OOS",
            "quality_gate": {"passed": False},
            "robustness": {"passed": True},
            "eligible_for_promotion_review": True,
        }
    )
    report = audit_envelope(envelope)
    assert report["ok"] is False
    assert any("promotion_eligibility_bypasses_required_gates" in reason for reason in report["failures"])


def test_audit_rejects_tampered_envelope():
    envelope = valid_payload()
    envelope["payload"]["results"].append({"ok": True})
    report = audit_envelope(envelope)
    assert report["ok"] is False
    assert report["failures"] == ["invalid_or_tampered_research_envelope"]

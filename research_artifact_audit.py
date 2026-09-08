"""Independent fail-closed audit of cloud research artifacts.

The audit never promotes or edits strategies. It verifies sealed artifacts and
key safety invariants in a separate process before evidence is trusted by later
review stages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_artifact import verify_research_envelope


def audit_envelope(envelope):
    failures = []
    if not verify_research_envelope(envelope):
        return {"ok": False, "failures": ["invalid_or_tampered_research_envelope"], "checked_results": 0}

    payload = envelope.get("payload") or {}
    results = payload.get("results") or []
    for item_index, item in enumerate(results):
        if not item.get("ok"):
            continue
        execution = item.get("execution_oos_robustness")
        if execution:
            prefix = f"result[{item_index}].execution_oos_robustness"
            if execution.get("research_only") is not True:
                failures.append(f"{prefix}.research_only_not_true")
            if execution.get("historical_slippage_available") is not False:
                failures.append(f"{prefix}.historical_slippage_must_remain_unavailable")
            if execution.get("same_trade_path_policy") is not True:
                failures.append(f"{prefix}.same_trade_path_policy_not_true")
            anchor = execution.get("current_snapshot_anchor") or {}
            if anchor.get("available") and anchor.get("historical") is not False:
                failures.append(f"{prefix}.live_snapshot_misrepresented_as_historical")

        registry = (item.get("strategy_registry") or {}).get("registry") or []
        for strategy_index, strategy in enumerate(registry):
            prefix = f"result[{item_index}].strategy[{strategy_index}]"
            gate_passed = bool((strategy.get("quality_gate") or {}).get("passed"))
            robust_passed = bool((strategy.get("robustness") or {}).get("passed"))
            eligible = strategy.get("eligible_for_promotion_review") is True
            status = strategy.get("status")
            if eligible and not (gate_passed and robust_passed and status == "ROBUST_OOS"):
                failures.append(f"{prefix}.promotion_eligibility_bypasses_required_gates")
            if status == "ROBUST_OOS" and not eligible:
                failures.append(f"{prefix}.robust_status_without_promotion_review_eligibility")
            if not gate_passed and eligible:
                failures.append(f"{prefix}.failed_quality_gate_marked_eligible")
            if (strategy.get("robustness") or {}).get("status") == "SKIPPED_QUALITY_GATE_FAILED" and eligible:
                failures.append(f"{prefix}.skipped_robustness_marked_eligible")

    return {"ok": not failures, "failures": failures, "checked_results": len(results)}


def audit_paths(root):
    root = Path(root)
    files = sorted(root.rglob("backtest_results.json")) if root.is_dir() else [root]
    reports = []
    for path in files:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            report = audit_envelope(envelope)
        except Exception as exc:
            report = {"ok": False, "failures": [f"{type(exc).__name__}:artifact_unreadable"], "checked_results": 0}
        reports.append({"path": str(path), **report})
    if not files:
        reports.append({"path": str(root), "ok": False, "failures": ["no_backtest_results_found"], "checked_results": 0})
    return {"ok": all(report["ok"] for report in reports), "artifacts": reports}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="research_output/adversarial_audit.json")
    args = parser.parse_args()
    report = audit_paths(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

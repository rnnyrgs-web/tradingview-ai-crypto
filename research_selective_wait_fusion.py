"""Research-only fusion of restrictive signal-quality diagnostics.

This combines independent research diagnostics into prioritized abstention
hypotheses. It never changes a production action, opens untouched OOS, mutates a
strategy, or grants trade/promotion authority.
"""

from __future__ import annotations

from collections import defaultdict

from signal_development import objective_reference


def _add(votes, key, source, samples, detail):
    item = votes[key]
    item["sources"].add(source)
    item["supporting_samples"] += int(samples or 0)
    item["details"].append(detail)


def build_selective_wait_fusion(*, meta_wait, regime_strategy, economic_calibration, microstructure_veto, error_attribution):
    votes = defaultdict(lambda: {"sources": set(), "supporting_samples": 0, "details": []})

    for row in (meta_wait or {}).get("groups") or []:
        expectancy = row.get("after_cost_expectancy_pct")
        if row.get("ready_for_research") and expectancy is not None and float(expectancy) <= 0.0:
            horizon = str(row.get("horizon") or "unknown")
            key = f"meta_wait:{horizon}:{row.get('dimension')}={row.get('group')}"
            _add(votes, key, "meta_wait", row.get("samples"), row)

    for horizon, report in ((regime_strategy or {}).get("horizons") or {}).items():
        for row in report.get("pairs") or []:
            if row.get("candidate_status") == "RESTRICTIVE_WAIT_CANDIDATE":
                key = f"regime_strategy:{horizon}:{row.get('market_regime')}:{row.get('strategy_identity')}"
                _add(votes, key, "regime_strategy", (row.get("validation") or {}).get("samples"), row)

    for horizon, report in ((economic_calibration or {}).get("horizons") or {}).items():
        for row in report.get("confidence_bands") or []:
            if row.get("candidate_status") == "RESTRICTIVE_WAIT_CANDIDATE":
                key = f"economic_calibration:{horizon}:{row.get('confidence_band')}"
                _add(votes, key, "economic_calibration", (row.get("validation") or {}).get("samples"), row)

    for row in (microstructure_veto or {}).get("groups") or []:
        if row.get("candidate_status") == "RESTRICTIVE_VETO_CANDIDATE":
            key = f"microstructure:{row.get('microstructure_state')}"
            _add(votes, key, "microstructure_veto", row.get("samples"), row)

    for row in (error_attribution or {}).get("research_priorities") or []:
        if row.get("reason") in {
            "strategy_deterioration",
            "regime_mismatch",
            "execution_spread_stress",
            "thin_visible_liquidity",
            "high_confidence_false_positive",
        }:
            key = f"error_attribution:{row.get('reason')}"
            _add(votes, key, "error_attribution", row.get("independent_error_samples"), row)

    hypotheses = []
    for key, item in votes.items():
        sources = sorted(item["sources"])
        hypotheses.append({
            "hypothesis_id": key,
            "independent_diagnostic_sources": sources,
            "source_count": len(sources),
            "supporting_samples": item["supporting_samples"],
            "priority_score": len(sources) * 1000 + item["supporting_samples"],
            "recommended_action": "PREDECLARE_RESTRICTIVE_WAIT_EXPERIMENT",
            "requires_fresh_validation": True,
            "requires_untouched_oos": True,
            "requires_multiple_testing_protection": True,
            "details": item["details"],
            "trade_authority": False,
            "promotion_authority": False,
        })
    hypotheses.sort(key=lambda x: (-x["priority_score"], x["hypothesis_id"]))

    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("selective-wait-fusion", "learning_diagnostics"),
        "restrictive_hypotheses": hypotheses,
        "policy": "Fusion ranks abstention experiments only. Agreement between diagnostics is not proof and cannot alter production without the canonical validation chain. Horizon-specific evidence is never pooled across 24h and 7d.",
        "untouched_oos_opened": False,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
    }

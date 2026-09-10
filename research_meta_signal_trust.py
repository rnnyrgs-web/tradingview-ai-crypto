"""Research-only A+ meta-signal trust diagnostics.

This layer evaluates fixed, predeclared trust profiles on independent resolved
forecasts. It is deliberately NOT a production confidence score: untouched OOS
stays sealed, thresholds are not tuned on outcomes, and no result can authorize
trading or promotion.

The first profiles use only fields that can be proven available before forecast:
primary score and future-only cross-exchange market-consensus provenance. Other
evidence families (regime routing, ensemble diversity, microstructure) are
reported as readiness/supporting diagnostics but never treated as independent
confirmation unless their evidence is aligned and separately validated.
"""

from __future__ import annotations

from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

ROUND_TRIP_COST_PCT = 0.12
COST_STRESS_MULTIPLIERS = (1.0, 1.5, 2.0, 3.0)
MIN_DEVELOPMENT_SAMPLES = 12
MIN_VALIDATION_SAMPLES = 8
MIN_PRECISION_LIFT = 0.02
HIGH_CONFIDENCE_CUTOFF = 80.0


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _resolved_independent(rows, horizon):
    rows = [row for row in (rows or []) if row.get("horizon") == horizon and row.get("resolved_at") and isinstance(row.get("correct"), bool)]
    return _independent_rows(rows, horizon)


def _split(rows):
    n = len(rows)
    if not n:
        return [], [], []
    dev_end = max(1, int(n * 0.60))
    val_end = max(dev_end, int(n * 0.80))
    if n >= 3:
        val_end = min(n - 1, max(dev_end + 1, val_end))
    return rows[:dev_end], rows[dev_end:val_end], rows[val_end:]


def _actionable(row):
    return str(row.get("action_at_forecast") or "").upper() not in {"WAIT", "NO_TRADE", "RESEARCH_ONLY"}


def _high_confidence(row):
    score = _finite(row.get("score"))
    return score is not None and score >= HIGH_CONFIDENCE_CUTOFF


def _consensus_reliable(row):
    if row.get("market_consensus_timestamp_safe") is not True or row.get("market_consensus_reliable") is not True:
        return False
    try:
        sources = int(row.get("market_consensus_source_count") or 0)
        required = int(row.get("market_consensus_required_source_count") or 0)
    except (TypeError, ValueError):
        return False
    return required >= 2 and sources >= required


def _profile_rows(rows, profile):
    actionable = [row for row in rows if _actionable(row)]
    if profile == "BASE_ACTIONABLE":
        return actionable
    if profile == "HIGH_CONFIDENCE":
        return [row for row in actionable if _high_confidence(row)]
    if profile == "HIGH_CONFIDENCE_CONSENSUS":
        return [row for row in actionable if _high_confidence(row) and _consensus_reliable(row)]
    raise ValueError(f"unknown trust profile: {profile}")


def _metrics(rows, *, cost_pct=ROUND_TRIP_COST_PCT):
    total = len(rows)
    returns = [_finite(row.get("directional_return_pct")) for row in rows]
    complete = bool(total and all(value is not None for value in returns))
    precision = sum(1 for row in rows if row.get("correct") is True) / total if total else None
    stress = {}
    if complete:
        gross = sum(float(value) for value in returns) / total
        for multiplier in COST_STRESS_MULTIPLIERS:
            stress[f"{multiplier:g}x"] = round(gross - float(cost_pct) * multiplier, 4)
    return {"samples": total, "directional_precision": round(precision, 4) if precision is not None else None, "economic_evidence_complete": complete, "cost_stress_expected_value_pct": stress, "base_after_cost_expectancy_pct": stress.get("1x"), "worst_case_after_cost_expectancy_pct": stress.get("3x")}


def _precision_lift(profile_metrics, baseline_metrics):
    p = profile_metrics.get("directional_precision")
    b = baseline_metrics.get("directional_precision")
    if p is None or b is None:
        return None
    return round(float(p) - float(b), 4)


def _status(profile, dev, val, dev_base, val_base):
    if dev["samples"] < MIN_DEVELOPMENT_SAMPLES or val["samples"] < MIN_VALIDATION_SAMPLES:
        return "INSUFFICIENT_INDEPENDENT_EVIDENCE"
    if not dev["economic_evidence_complete"] or not val["economic_evidence_complete"]:
        return "INSUFFICIENT_ECONOMIC_EVIDENCE"
    dev_lift = _precision_lift(dev, dev_base)
    val_lift = _precision_lift(val, val_base)
    if dev_lift is None or val_lift is None:
        return "INSUFFICIENT_BASELINE_EVIDENCE"
    dev_ev = dev.get("base_after_cost_expectancy_pct")
    val_ev = val.get("base_after_cost_expectancy_pct")
    if dev_ev is not None and val_ev is not None and float(dev_ev) <= 0 and float(val_ev) <= 0:
        return "RESTRICTIVE_WAIT_CANDIDATE"
    robust = dev_lift >= MIN_PRECISION_LIFT and val_lift >= MIN_PRECISION_LIFT and float(dev.get("worst_case_after_cost_expectancy_pct") or -1e9) > 0.0 and float(val.get("worst_case_after_cost_expectancy_pct") or -1e9) > 0.0
    if robust:
        return "A_PLUS_PROFILE_RESEARCH_CANDIDATE" if profile == "HIGH_CONFIDENCE_CONSENSUS" else "A_PROFILE_RESEARCH_CANDIDATE"
    return "NO_STABLE_TRUST_EDGE"


def _supporting_readiness(regime_strategy, ensemble_diversity, microstructure_veto):
    regime_candidates = 0
    regime_waits = 0
    for report in ((regime_strategy or {}).get("horizons") or {}).values():
        for row in report.get("pairs") or []:
            status = row.get("candidate_status")
            regime_candidates += int(status == "PROSPECTIVE_SHADOW_ROUTER_CANDIDATE")
            regime_waits += int(status == "RESTRICTIVE_WAIT_CANDIDATE")
    return {"regime_router_candidates": regime_candidates, "regime_restrictive_wait_candidates": regime_waits, "ensemble_diversity_pairs_measured": len((ensemble_diversity or {}).get("pairs") or []), "prospective_microstructure_samples": int((microstructure_veto or {}).get("samples_with_microstructure") or 0), "policy": "These families are supporting readiness only and are not counted as independent confirmation by this version of the trust layer."}


def build_meta_signal_trust(rows, *, regime_strategy=None, ensemble_diversity=None, microstructure_veto=None, cost_pct=ROUND_TRIP_COST_PCT):
    horizons = {}
    sealed = 0
    profiles = ("BASE_ACTIONABLE", "HIGH_CONFIDENCE", "HIGH_CONFIDENCE_CONSENSUS")
    for horizon in ("24h", "7d"):
        independent = _resolved_independent(rows, horizon)
        development, validation, untouched_oos = _split(independent)
        sealed += len(untouched_oos)
        dev_base = _metrics(_profile_rows(development, "BASE_ACTIONABLE"), cost_pct=cost_pct)
        val_base = _metrics(_profile_rows(validation, "BASE_ACTIONABLE"), cost_pct=cost_pct)
        reports = []
        for profile in profiles:
            dev = _metrics(_profile_rows(development, profile), cost_pct=cost_pct)
            val = _metrics(_profile_rows(validation, profile), cost_pct=cost_pct)
            status = "BASELINE_REFERENCE" if profile == "BASE_ACTIONABLE" else _status(profile, dev, val, dev_base, val_base)
            reports.append({"profile": profile, "development": dev, "validation": val, "development_precision_lift_vs_actionable": _precision_lift(dev, dev_base), "validation_precision_lift_vs_actionable": _precision_lift(val, val_base), "candidate_status": status, "requires_untouched_oos": status in {"A_PROFILE_RESEARCH_CANDIDATE", "A_PLUS_PROFILE_RESEARCH_CANDIDATE", "RESTRICTIVE_WAIT_CANDIDATE"}, "requires_robustness": status in {"A_PROFILE_RESEARCH_CANDIDATE", "A_PLUS_PROFILE_RESEARCH_CANDIDATE", "RESTRICTIVE_WAIT_CANDIDATE"}, "requires_genuine_forward_replication": True, "trade_authority": False, "promotion_authority": False})
        horizons[horizon] = {"independent_samples": len(independent), "development_samples": len(development), "validation_samples": len(validation), "untouched_oos_samples_sealed": len(untouched_oos), "profiles": reports}
    return {"ok": True, "research_only": True, "objective": objective_reference("a-plus-meta-signal-trust", "learning_diagnostics"), "predeclared_high_confidence_cutoff": HIGH_CONFIDENCE_CUTOFF, "minimum_precision_lift": MIN_PRECISION_LIFT, "minimum_development_samples": MIN_DEVELOPMENT_SAMPLES, "minimum_validation_samples": MIN_VALIDATION_SAMPLES, "cost_stress_multipliers": list(COST_STRESS_MULTIPLIERS), "a_plus_definition": "High-confidence + timestamp-safe multi-source market consensus; >=2pp precision lift in development and validation; positive expectancy through 3x fixed cost stress. Research candidate only.", "untouched_oos_outcomes_scored": False, "untouched_oos_samples_sealed": sealed, "supporting_evidence_readiness": _supporting_readiness(regime_strategy, ensemble_diversity, microstructure_veto), "horizons": horizons, "trade_authority": False, "promotion_authority": False, "strategy_mutation_authority": False, "automatic_execution_authority": False, "live_label_allowed": False}

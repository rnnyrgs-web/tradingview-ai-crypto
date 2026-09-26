"""Portfolio NAV metrics and additive money attribution, never win-count ranking."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt

from .contracts import (COSTS, DEVELOPMENT, SAFE, experiment_id, independent_blocks,
                        net_pnl, timestamp, validate_experiment)


def _calendar_returns(equity, period):
    buckets = {}
    for row in equity:
        at = timestamp(row["timestamp"])
        if period == "day":
            key = at.date().isoformat()
        elif period == "week":
            key = f"{at.isocalendar().year}-W{at.isocalendar().week:02}"
        else:
            key = at.strftime("%Y-%m")
        buckets[key] = row["nav"]
    previous, returns = equity[0]["nav"], {}
    for key, nav in buckets.items():
        returns[key] = nav / previous - 1 if previous > 0 else 0.0
        previous = nav
    return returns


def _metrics(e):
    trades, equity, c = e["trades"], e["equity"], e["contract"]
    initial, final = c["initial_capital"], equity[-1]["nav"]
    pnls = [net_pnl(t) for t in trades]
    peak, max_dd, recovery = initial, 0.0, 0.0
    peak_at = timestamp(equity[0]["timestamp"])
    underwater = False
    returns, weighted_exposure = [], 0.0
    for i, row in enumerate(equity):
        at, nav = timestamp(row["timestamp"]), row["nav"]
        if nav >= peak:
            if underwater:
                recovery = max(recovery, (at - peak_at).total_seconds())
            peak, peak_at, underwater = nav, at, False
        else:
            underwater = True
            max_dd = max(max_dd, 1 - nav / peak)
            recovery = max(recovery, (at - peak_at).total_seconds())
        if i:
            prior = equity[i - 1]
            returns.append(nav / prior["nav"] - 1 if prior["nav"] else 0.0)
            weighted_exposure += prior["gross_exposure"] * (at - timestamp(prior["timestamp"])).total_seconds()
    duration = (timestamp(c["end"]) - timestamp(c["start"])).total_seconds()
    total_return = final / initial - 1
    cost = {k: sum(t["costs"][k] for t in trades) for k in COSTS}
    worst_tail = sorted(pnls)[:max(1, (len(pnls) + 19) // 20)]
    periods = {p: _calendar_returns(equity, p) for p in ("day", "week", "month")}
    blocks = independent_blocks(trades)
    return {
        "net_pnl": final - initial, "compounded_net_return": total_return,
        "cagr": (final / initial) ** (365.25 * 86400 / duration) - 1 if duration >= 365.25 * 86400 else None,
        "max_drawdown": max_dd, "return_over_max_drawdown": total_return / max_dd if max_dd else None,
        "downside_rms_per_observed_interval": sqrt(sum(min(0, r) ** 2 for r in returns) / len(returns)),
        "worst_trade_money": min(pnls, default=None),
        "worst_event_money": min((sum(net_pnl(t) for t in block) for block in blocks), default=None),
        "tail_expected_shortfall_5pct_trade_money": sum(worst_tail) / len(worst_tail) if worst_tail else None,
        "max_recovery_or_underwater_seconds": recovery, "currently_underwater": underwater,
        "chronological_returns": periods,
        "worst_observed_calendar_return": {p: min(r.values(), default=None) for p, r in periods.items()},
        "positive_observed_month_fraction": sum(x > 0 for x in periods["month"].values()) / len(periods["month"]),
        "after_cost_expectancy_money": sum(pnls) / len(pnls) if pnls else None,
        "average_gross_exposure_over_initial_capital": weighted_exposure / duration / initial,
        "turnover_one_way_notional_over_initial_capital": 2 * sum(t["notional"] for t in trades) / initial,
        "costs": cost, "sample_count": len(trades), "independent_event_count": len(blocks),
        "win_rate_diagnostic": sum(x > 0 for x in pnls) / len(pnls) if pnls else None,
        "nav_sampling": "observed marks; drawdown is a sampled lower bound; partial calendar periods included",
    }


def _attribution(e):
    groups = defaultdict(lambda: defaultdict(list))
    for t in e["trades"]:
        for name in ("asset", "timeframe", "direction"):
            groups[name][t[name]].append(t)
        for name, f in t["features"].items():
            # Reserved dimensions cannot be overwritten by arbitrary feature labels.
            key = f"feature:{name}" if name in {"asset", "timeframe", "direction"} else name
            groups[key][f["value"]].append(t)
    output = {}
    for dimension, values in sorted(groups.items()):
        output[dimension] = {}
        for value, rows in sorted(values.items()):
            pnl = sum(net_pnl(t) for t in rows)
            output[dimension][value] = {
                "net_pnl": pnl, "contribution_to_initial_capital": pnl / e["contract"]["initial_capital"],
                "sample_count": len(rows), "independent_event_count": len(independent_blocks(rows)),
                "costs": {k: sum(t["costs"][k] for t in rows) for k in COSTS},
            }
    return output


def analyze(experiment):
    e = validate_experiment(experiment)
    c = e["contract"]
    base = {"schema_version": 1, "experiment_id": experiment_id(c), "contract": c,
            "outcome": "INCONCLUSIVE", "source_status": e["status"],
            "development_learning_allowed": c["split"] in DEVELOPMENT,
            "metrics": {}, "attribution": {}, "risk_flags": [], "concentration": {},
            "economic_assessment": "UNKNOWN", "failure_reasons": list(e["failure_reasons"]),
            "component_evidence": [], "interaction_evidence": [],
            "unavailable_metrics": ["capacity", "execution_fill_audit", "cross_engine_stability",
                                    "walk_forward_stability"], **SAFE}
    if e["status"] == "INFRA_DATA_FAILURE":
        return {**base, "outcome": "INFRA_DATA_FAILURE"}
    metrics = _metrics(e)
    pnls = [net_pnl(t) for t in e["trades"]]
    independent_event_pnls = [
        sum(net_pnl(t) for t in block)
        for block in independent_blocks(e["trades"])
    ]
    positive = sum(max(0, x) for x in pnls)
    best = max(pnls, default=0)
    positive_events = sum(max(0, x) for x in independent_event_pnls)
    best_event = max(independent_event_pnls, default=0)
    cost_burden = sum(metrics["costs"].values())
    concentration = {
        "largest_winner_share": max(0, best) / positive if positive else 0,
        "net_pnl_without_best_trade": metrics["net_pnl"] - best,
        "largest_independent_event_profit_share": (
            max(0, best_event) / positive_events if positive_events else 0
        ),
        "net_pnl_without_best_independent_event": metrics["net_pnl"] - best_event,
        "net_pnl_at_double_variable_cost": metrics["net_pnl"] - cost_burden,
        "sensitivity_note": (
            "Arithmetic P&L sensitivity only; independent events conservatively combine "
            "same-ID and overlapping intervals; not a rerun or altered NAV path."
        ),
    }
    flags = []
    if e["equity"][-1]["nav"] == 0:
        flags.append("INSOLVENT")
    event_tail = metrics["worst_event_money"]
    if (metrics["max_drawdown"] >= .5
            or min(pnls, default=0) / c["initial_capital"] <= -.2
            or (event_tail is not None and event_tail / c["initial_capital"] <= -.2)):
        flags.append("CATASTROPHIC_LOSS")
    if positive and concentration["largest_winner_share"] > .5:
        flags.append("SINGLE_WINNER_CONCENTRATION")
    if (metrics["net_pnl"] > 0
            and concentration["net_pnl_without_best_independent_event"] <= 0):
        flags.append("SINGLE_WINNER_DEPENDENCE")
    if metrics["net_pnl"] > 0 and concentration["net_pnl_at_double_variable_cost"] <= 0:
        flags.append("COST_SENSITIVE")
    attribution = _attribution(e) if c["split"] != "RELEASED_OOS" else {}
    for dimension in ("asset", "regime"):
        values = attribution.get(dimension, {})
        gains = [max(0, x["net_pnl"]) for x in values.values()]
        share = max(gains, default=0) / sum(gains) if sum(gains) else None
        concentration[f"{dimension}_positive_contribution_share"] = share
        if share is not None and share > .8:
            flags.append(f"{dimension.upper()}_CONCENTRATION")
    monthly = metrics["chronological_returns"]["month"]
    if len(monthly) > 1:
        gains = [max(0, x) for x in monthly.values()]
        if sum(gains) and max(gains) / sum(gains) > .8:
            flags.append("SHORT_PERIOD_CONCENTRATION")
    if metrics["independent_event_count"] < c["minimum_events"]:
        flags.append("INSUFFICIENT_INDEPENDENT_EVENTS")
    assessment = "POSITIVE_AFTER_COST_UNVALIDATED" if metrics["net_pnl"] > 0 else "NEGATIVE_AFTER_COST"
    return {**base, "metrics": metrics, "attribution": attribution, "risk_flags": flags,
            "concentration": concentration, "economic_assessment": assessment,
            "success_learning": {"return_sources": attribution,
                "falsifier": "Frozen replication fails after costs on fresh chronological evidence.",
                "next_test": "Independent chronological replication under unchanged validation gates."} if e["status"] == "PASSED" else None}

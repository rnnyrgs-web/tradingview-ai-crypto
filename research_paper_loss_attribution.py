"""Research-only attribution of closed paper-trade losses into falsifiable priorities.

Closed paper trades are genuine forward execution/P&L observations. This module
turns recurring observed loss conditions into predeclared research questions; it
never claims causality from missing metadata and never grants trade/promotion
authority.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

MIN_PAPER_GROUP_SAMPLES = 5


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _invalid_ranking_fields(row):
    fields = (
        "economic_harm_usd",
        "economic_harm_score_pct",
        "priority_score",
        "independent_samples",
    )
    return [
        field
        for field in fields
        if field in row and row.get(field) is not None and _finite(row.get(field)) is None
    ]


def _finite_ranking_values(row):
    return not _invalid_ranking_fields(row)


def _closed(rows):
    return [row for row in (rows or []) if str(row.get("status") or "").upper() == "CLOSED" and _finite(row.get("pnl_usd")) is not None]


def _exit_group(row):
    reason = str(row.get("exit_reason") or "UNKNOWN").strip().upper() or "UNKNOWN"
    slippage = _finite(row.get("exit_slippage_bps"))
    if slippage is not None and slippage >= 35:
        return f"{reason}:HIGH_EXIT_SLIPPAGE"
    return reason


def _group_metrics(rows, key_fn, dimension, minimum_samples):
    buckets = defaultdict(list)
    for row in rows:
        buckets[str(key_fn(row) or "unknown")].append(row)
    out = []
    for group, members in buckets.items():
        pnls = [_finite(row.get("pnl_usd")) for row in members]
        pnls = [value for value in pnls if value is not None]
        pct = [_finite(row.get("pnl_pct")) for row in members]
        pct = [value for value in pct if value is not None]
        losses = [value for value in pnls if value < 0]
        loss_rate = len(losses) / len(pnls) if pnls else 0.0
        total_loss_usd = -sum(losses)
        net_pnl_usd = sum(pnls)
        loss_pct_harm = -sum(value for value in pct if value < 0)
        ready = len(pnls) >= int(minimum_samples) and bool(losses)
        horizon = group if dimension == "paper_horizon" and group in {"24h", "7d"} else "both"
        question = (
            f"Can a predeclared restrictive filter or challenger reduce paper-trade losses for "
            f"{dimension}={group} without destroying after-cost expectancy or actionable coverage?"
        )
        out.append({
            "dimension": dimension,
            "group": group,
            "samples": len(pnls),
            "independent_samples": len(pnls),
            "losses": len(losses),
            "wrong_rate": round(loss_rate, 4),
            "priority_score": round(loss_rate * min(len(pnls), 100), 4),
            "net_pnl_usd": round(net_pnl_usd, 2),
            "economic_harm_usd": round(total_loss_usd, 2),
            "economic_harm_score_pct": round(max(0.0, loss_pct_harm), 4),
            "average_after_cost_return_pct": round(sum(pct) / len(pct), 4) if pct else None,
            "research_question": question,
            "hypothesis": question,
            "predicted_mechanism": (
                f"The observed paper-trade condition {dimension}={group} is associated with recurring forward losses; "
                "a restrictive abstention rule, entry filter, exit change, or independent challenger may reduce economic harm."
            ),
            "target_horizon": horizon,
            "expected_signal_quality_effect": "Increase genuine forward after-cost expectancy first; preserve useful coverage second.",
            "evidence_needed": [
                "closed forward paper trades",
                "chronological backtest of the predeclared intervention",
                "untouched OOS",
                "realistic execution costs",
                "fresh forward shadow comparison against the unchanged champion",
            ],
            "falsification_criteria": [
                "no stable after-cost improvement",
                "loss reduction is offset by worse expectancy or drawdown",
                "benefit disappears on untouched OOS or fresh forward paper evidence",
            ],
            "chronological_oos_requirements": ["purged chronological train/validation", "untouched OOS not reused for tuning"],
            "realistic_cost_treatment": ["fees, spread, slippage and funding where applicable"],
            "independent_sample_requirements": [f"at least {minimum_samples} closed forward paper trades in the observed group before queueing"],
            "status": "HYPOTHESIS_FROM_FORWARD_PAPER_PNL",
            "result": None,
            "evidence_conclusion": "unresolved",
            "requires_new_validation": ready,
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "automatic_strategy_mutation": False,
        })
    return out


def build_paper_loss_attribution(rows, *, minimum_samples=MIN_PAPER_GROUP_SAMPLES):
    closed = _closed(rows)
    dimensions = {
        "paper_exit_condition": _group_metrics(closed, _exit_group, "paper_exit_condition", minimum_samples),
        "paper_horizon": _group_metrics(closed, lambda row: str(row.get("horizon") or "unknown"), "paper_horizon", minimum_samples),
        "paper_direction": _group_metrics(closed, lambda row: str(row.get("direction") or "unknown").upper(), "paper_direction", minimum_samples),
    }
    priorities = [
        item
        for metrics in dimensions.values()
        for item in metrics
        if item.get("requires_new_validation") is True
    ]
    priorities.sort(
        key=lambda item: (
            -float(item.get("economic_harm_usd") or 0.0),
            -float(item.get("economic_harm_score_pct") or 0.0),
            -float(item.get("wrong_rate") or 0.0),
            -int(item.get("samples") or 0),
            str(item.get("dimension") or ""),
            str(item.get("group") or ""),
        )
    )
    return {
        "ok": True,
        "research_only": True,
        "closed_paper_trades": len(closed),
        "paper_losses": sum(1 for row in closed if (_finite(row.get("pnl_usd")) or 0.0) < 0),
        "dimensions": dimensions,
        "research_priorities": priorities[:20],
        "priority_basis": "realized forward paper economic harm first, then loss rate and sample size",
        "causality_policy": "Exit reason/slippage/horizon/direction are observed conditions, not asserted root causes. Missing causes remain unknown until separately validated.",
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
    }


def merge_paper_priorities(diagnostics, paper_report, *, limit=20):
    merged = dict(diagnostics or {})
    priorities = []
    invalid_rows = []
    for source, rows in (
        ("diagnostics", merged.get("research_priorities") or []),
        ("paper_report", paper_report.get("research_priorities") or []),
    ):
        for source_index, row in enumerate(rows):
            if not isinstance(row, dict):
                invalid_rows.append({
                    "source": source,
                    "source_index": source_index,
                    "dimension": None,
                    "group": None,
                    "invalid_fields": [],
                    "reason": "malformed_priority_row",
                })
                continue
            invalid_fields = _invalid_ranking_fields(row)
            if invalid_fields:
                invalid_rows.append({
                    "source": source,
                    "source_index": source_index,
                    "dimension": row.get("dimension"),
                    "group": row.get("group"),
                    "invalid_fields": invalid_fields,
                    "reason": "nonfinite_ranking_value",
                })
                continue
            priorities.append(dict(row))
    priorities.sort(
        key=lambda row: (
            -float(row.get("economic_harm_usd") or 0.0),
            -float(row.get("economic_harm_score_pct") or 0.0),
            -float(row.get("priority_score") or 0.0),
            -int(row.get("independent_samples") or 0),
        )
    )
    merged["research_priorities"] = priorities[: max(0, int(limit))]
    merged["invalid_priority_rows"] = invalid_rows
    merged["paper_trade_feedback"] = {
        "closed_paper_trades": paper_report.get("closed_paper_trades", 0),
        "paper_losses": paper_report.get("paper_losses", 0),
        "priority_count": len(paper_report.get("research_priorities") or []),
    }
    return merged

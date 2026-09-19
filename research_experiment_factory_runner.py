"""Lightweight runner that turns resolved forecasts and paper P&L into a bounded quant-science queue."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
from paper_db import fetch_all_paper_trades
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_learning import learning_diagnostics
from research_learning_state import load_state
from research_paper_loss_attribution import build_paper_loss_attribution, merge_paper_priorities
from research_quant_science_factory import build_quant_science_queue
from research_specialist_bridge import enrich_diagnostics_with_specialists
from profitability_learning.runtime import apply_queue_feedback, factory_feedback


def build_factory_report(rows, paper_trades=None):
    paper_loss = build_paper_loss_attribution(paper_trades or [])
    diagnostics = merge_paper_priorities(learning_diagnostics(rows), paper_loss)
    diagnostics, specialist_bridge = enrich_diagnostics_with_specialists(rows, diagnostics)
    memory = load_state()
    queue = apply_queue_feedback(build_quant_science_queue(diagnostics, memory))
    heavy_dispatch_plan = build_heavy_dispatch_plan(queue)
    return {
        "ok": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "automatic_execution_authority": False,
        "resolved_samples": diagnostics.get("resolved_samples"),
        "baseline_precision": diagnostics.get("baseline_precision"),
        "paper_trade_loss_attribution": paper_loss,
        "research_priorities": (diagnostics.get("research_priorities") or [])[:10],
        "specialist_bridge": specialist_bridge,
        "quant_science_queue": queue,
        "experiment_queue": queue,
        "heavy_dispatch_plan": heavy_dispatch_plan,
        "profitability_learning": factory_feedback(),
    }


def _bounded_limit(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def main():
    # A strategy queue only needs a bounded recent evidence window. Pulling the
    # entire prediction/paper ledgers on every lightweight cycle created large
    # repeated database egress without adding independent information.
    ledger_limit = _bounded_limit("RESEARCH_EXPERIMENT_LEDGER_LIMIT", 500, 100, 2000)
    paper_limit = _bounded_limit("RESEARCH_EXPERIMENT_PAPER_LIMIT", 500, 50, 2000)
    rows = fetch_shadow_predictions(limit=ledger_limit)
    paper_trades = fetch_all_paper_trades(limit=paper_limit)
    report = build_factory_report(rows, paper_trades)
    summary_path = os.getenv("RESEARCH_EXPERIMENT_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

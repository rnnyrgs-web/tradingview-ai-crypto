"""Lightweight runner that turns resolved-signal diagnostics into a bounded quant-science queue."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_learning import learning_diagnostics
from research_learning_state import load_state
from research_quant_science_factory import build_quant_science_queue


def build_factory_report(rows):
    diagnostics = learning_diagnostics(rows)
    memory = load_state()
    queue = build_quant_science_queue(diagnostics, memory)
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
        "research_priorities": (diagnostics.get("research_priorities") or [])[:10],
        "quant_science_queue": queue,
        "experiment_queue": queue,
        "heavy_dispatch_plan": heavy_dispatch_plan,
    }


def main():
    rows = fetch_shadow_predictions(limit=10000)
    report = build_factory_report(rows)
    summary_path = os.getenv("RESEARCH_EXPERIMENT_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

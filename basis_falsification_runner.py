"""Bounded research-only runtime for COORD-DATA-003 / DATA-BASIS-001.

This runner makes the already-frozen stage-1 falsification executable inside the
existing worker army. It has no signal, paper, promotion, broker, or live-trade
authority and writes only a compact evidence summary for coordinator diagnostics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from basis_falsification_research import evaluate_primary_horizons
from basis_history_research import collect_okx_basis_history

SUMMARY_ENV = "BASIS_FALSIFICATION_SUMMARY_PATH"
DEFAULT_BASE = "BTC"
DEFAULT_TARGET_POINTS = 1000
DEFAULT_MAX_PAGES = 20


def run() -> dict:
    base = str(os.getenv("BASIS_RESEARCH_BASE", DEFAULT_BASE)).upper().strip()
    target_points = int(os.getenv("BASIS_RESEARCH_TARGET_POINTS", str(DEFAULT_TARGET_POINTS)))
    max_pages = int(os.getenv("BASIS_RESEARCH_MAX_PAGES", str(DEFAULT_MAX_PAGES)))

    dataset = collect_okx_basis_history(base, target_points=target_points, max_pages=max_pages)
    evaluation = evaluate_primary_horizons(dataset)
    results = evaluation.get("results") if isinstance(evaluation.get("results"), dict) else {}
    available_results = sum(1 for row in results.values() if isinstance(row, dict) and row.get("available") is True)

    return {
        "research_only": True,
        "task_id": "COORD-DATA-003",
        "candidate_id": "DATA-BASIS-001",
        "base": base,
        "evidence_conclusion": "stage1_evaluated" if available_results else "insufficient_evidence",
        "collection": {
            "available": dataset.get("available") is True,
            "reason": dataset.get("reason"),
            "target_points": dataset.get("target_points"),
            "point_count": dataset.get("point_count"),
            "mark_point_count": dataset.get("mark_point_count"),
            "index_point_count": dataset.get("index_point_count"),
            "mark_pages": dataset.get("mark_pages"),
            "index_pages": dataset.get("index_pages"),
            "alignment": dataset.get("alignment"),
            "completed_candles_only": dataset.get("completed_candles_only") is True,
            "interpolation_allowed": dataset.get("interpolation_allowed") is True,
        },
        "results": results,
        "available_primary_results": available_results,
        "production_authority": False,
        "signal_authority": False,
        "paper_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }


def main() -> int:
    summary_path = os.getenv(SUMMARY_ENV)
    if not summary_path:
        raise RuntimeError(f"{SUMMARY_ENV} is required")
    payload = run()
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

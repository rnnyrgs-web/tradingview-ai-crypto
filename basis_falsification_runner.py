"""Compatibility runtime for the reserved profitability-falsification lane.

DATA-BASIS-001 is permanently rejected.  The historical filename remains only
so the existing bounded worker slot can be reused without adding concurrency or
cost.  This runtime now executes frozen research-only DATA-FUNDING-001 using
actual realized OKX funding timestamps plus completed OKX index candles.

It has no signal, paper, promotion, broker, or live-trade authority and writes
only a compact evidence summary.  Raw market/funding rows are never emitted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from funding_falsification_research import evaluate_primary_horizons
from funding_history_research import collect_okx_funding_history

# Keep the existing transport variable so the worker army can consume the
# summary without a new lane or concurrency change.  The payload itself is
# explicitly DATA-FUNDING-001 and never masquerades as basis evidence.
SUMMARY_ENV = "BASIS_FALSIFICATION_SUMMARY_PATH"
DEFAULT_BASE = "BTC"
DEFAULT_FUNDING_TARGET_POINTS = 1200
DEFAULT_INDEX_TARGET_POINTS = 5000
DEFAULT_FUNDING_MAX_PAGES = 15
DEFAULT_INDEX_MAX_PAGES = 50


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _configured_evidence_window() -> tuple[int, int, int, int]:
    """Return bounded funding/index collection limits without tuning outcomes."""
    return (
        _bounded_int("FUNDING_RESEARCH_TARGET_POINTS", DEFAULT_FUNDING_TARGET_POINTS, 2, 2000),
        _bounded_int("FUNDING_RESEARCH_INDEX_TARGET_POINTS", DEFAULT_INDEX_TARGET_POINTS, 2, 5000),
        _bounded_int("FUNDING_RESEARCH_MAX_PAGES", DEFAULT_FUNDING_MAX_PAGES, 1, 20),
        _bounded_int("FUNDING_RESEARCH_INDEX_MAX_PAGES", DEFAULT_INDEX_MAX_PAGES, 1, 50),
    )


def run() -> dict:
    base = str(os.getenv("FUNDING_RESEARCH_BASE", DEFAULT_BASE)).upper().strip()
    funding_target, index_target, funding_pages, index_pages = _configured_evidence_window()

    dataset = collect_okx_funding_history(
        base,
        funding_target_points=funding_target,
        index_target_points=index_target,
        funding_max_pages=funding_pages,
        index_max_pages=index_pages,
    )
    evaluation = evaluate_primary_horizons(dataset)
    results = evaluation.get("results") if isinstance(evaluation.get("results"), dict) else {}
    available_results = sum(
        1 for row in results.values()
        if isinstance(row, dict) and row.get("available") is True
    )
    stage1_passes = sum(
        1 for row in results.values()
        if isinstance(row, dict) and row.get("stage1_pass") is True
    )

    if available_results:
        evidence_conclusion = "stage1_evaluated"
    else:
        evidence_conclusion = "insufficient_evidence"

    return {
        "research_only": True,
        "task_id": "COORD-DATA-004",
        "candidate_id": "DATA-FUNDING-001",
        "legacy_runtime_filename": "basis_falsification_runner.py",
        "base": base,
        "evidence_conclusion": evidence_conclusion,
        "collection": {
            "available": dataset.get("available") is True,
            "reason": dataset.get("reason"),
            "funding_point_count": dataset.get("funding_point_count"),
            "index_point_count": dataset.get("index_point_count"),
            "funding_pages": dataset.get("funding_pages"),
            "index_pages": dataset.get("index_pages"),
            "uses_actual_funding_timestamps": dataset.get("uses_actual_funding_timestamps") is True,
            "assumed_fixed_funding_interval": dataset.get("assumed_fixed_funding_interval") is True,
            "completed_price_candles_only": dataset.get("completed_price_candles_only") is True,
            "interpolation_allowed": dataset.get("interpolation_allowed") is True,
            "forward_fill_allowed": dataset.get("forward_fill_allowed") is True,
            "nearest_neighbor_matching": dataset.get("nearest_neighbor_matching") is True,
        },
        "results": results,
        "available_primary_results": available_results,
        "stage1_pass_count": stage1_passes,
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

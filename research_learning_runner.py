"""Lightweight read-only worker that learns from resolved forecasts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
from research_cross_sectional_diagnostics import build_cross_sectional_diagnostics
from research_economic_calibration import build_economic_calibration
from research_ensemble_diversity import build_ensemble_diversity
from research_error_attribution import build_error_attribution
from research_learning import learning_diagnostics
from research_learning_state import append_lesson, load_state
from research_meta_wait import build_meta_wait_diagnostics
from research_microstructure_veto import build_microstructure_veto
from research_regime_strategy_router import build_regime_strategy_router
from research_selective_wait_fusion import build_selective_wait_fusion
from selective_precision import selective_precision_summary


def _priority_lesson(report):
    priorities = report.get("research_priorities") or []
    if not priorities:
        return None
    top = priorities[0]
    identity = f"{top.get('dimension')}|{top.get('group')}"
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return {
        "fingerprint": fingerprint,
        "hypothesis": top.get("research_question"),
        "outcome": "diagnostic_priority_observed",
        "evidence_summary": {
            "dimension": top.get("dimension"),
            "group": top.get("group"),
            "samples": top.get("samples"),
            "wrong_rate": top.get("wrong_rate"),
            "priority_score": top.get("priority_score"),
        },
        "recommended_next_test": "Design a predeclared restrictive filter or challenger and validate it on fresh chronological/OOS evidence.",
    }


def build_learning_report(rows):
    diagnostics = learning_diagnostics(rows)
    selective = selective_precision_summary(rows)
    meta_wait = build_meta_wait_diagnostics(rows)
    regime_strategy = build_regime_strategy_router(rows)
    economic_calibration = build_economic_calibration(rows)
    cross_sectional = build_cross_sectional_diagnostics(rows)
    microstructure_veto = build_microstructure_veto(rows)
    ensemble_diversity = build_ensemble_diversity(rows)
    error_attribution = build_error_attribution(rows)
    selective_wait_fusion = build_selective_wait_fusion(
        meta_wait=meta_wait,
        regime_strategy=regime_strategy,
        economic_calibration=economic_calibration,
        microstructure_veto=microstructure_veto,
        error_attribution=error_attribution,
    )
    lesson = _priority_lesson(diagnostics)
    if lesson:
        append_lesson(lesson)
    memory = load_state()
    return {
        "ok": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
        "diagnostics": diagnostics,
        "selective_precision": selective,
        "meta_wait_economic_diagnostics": meta_wait,
        "regime_strategy_router": regime_strategy,
        "economic_calibration": economic_calibration,
        "cross_sectional_residual_diagnostics": cross_sectional,
        "microstructure_veto": microstructure_veto,
        "ensemble_diversity": ensemble_diversity,
        "resolved_error_attribution": error_attribution,
        "selective_wait_fusion": selective_wait_fusion,
        "research_memory": {
            "lesson_count": len(memory.get("lessons") or []),
            "updated_at": memory.get("updated_at"),
            "recent_lessons": (memory.get("lessons") or [])[-10:],
        },
    }


def main():
    rows = fetch_shadow_predictions(limit=10000)
    report = build_learning_report(rows)
    summary_path = os.getenv("RESEARCH_LEARNING_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

"""Heavy research-only runner for the adaptive accuracy experiment lane."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
from ffrizz_secondary_runner import run as run_ffrizz_secondary
from research_adaptive_accuracy import build_adaptive_accuracy_report
from research_learning_state import append_lesson, load_state


def _memory_summary(state):
    value = state if isinstance(state, dict) else {}
    try:
        conclusive_trial_count = max(0, int(value.get("conclusive_trial_count") or 0))
    except (TypeError, ValueError):
        conclusive_trial_count = 0
    return {
        "lesson_count": len(value.get("lessons") or []),
        "conclusive_trial_count": conclusive_trial_count,
        "updated_at": value.get("updated_at"),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
    }


def build_runner_report(rows):
    memory = load_state()
    report = build_adaptive_accuracy_report(rows, memory)
    lesson = report.get("memory_lesson")
    if isinstance(lesson, dict):
        append_lesson(lesson)
        refreshed = load_state()
        report["research_memory"] = _memory_summary(refreshed)
    else:
        report["research_memory"] = _memory_summary(memory)
    return report


def _ffrizz_forward_collection():
    """Collect FFriZz forward evidence inside the already-bounded heavy lane.

    This deliberately does not create another worker, Render service, concurrency
    slot, or production authority. Failures remain observable but cannot mutate
    the primary strategy or suppress the adaptive report.
    """
    try:
        report = run_ffrizz_secondary(persist=True)
    except Exception as exc:
        return {
            "ok": False,
            "research_only": True,
            "error_type": type(exc).__name__,
            "trade_authority": False,
            "promotion_authority": False,
        }
    forward = report.get("forward_evidence") if isinstance(report, dict) else {}
    return {
        "ok": True,
        "research_only": True,
        "system": report.get("system"),
        "generated_at": report.get("generated_at"),
        "eligible_shadow_forecasts": int((forward or {}).get("eligible_shadow_forecasts") or 0),
        "non_overlapping_full_horizon_buckets": (forward or {}).get("non_overlapping_full_horizon_buckets") is True,
        "wait_rows_persisted": (forward or {}).get("wait_rows_persisted") is True,
        "historical_oi_backfill_used": (forward or {}).get("historical_oi_backfill_used") is True,
        "trade_authority": False,
        "promotion_authority": False,
    }


def main():
    rows = fetch_shadow_predictions(limit=10000)
    report = build_runner_report(rows)
    report["ffrizz_forward_collection"] = _ffrizz_forward_collection()
    summary_path = os.getenv("RESEARCH_ADAPTIVE_ACCURACY_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

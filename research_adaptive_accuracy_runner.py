"""Heavy research-only runner for the adaptive accuracy experiment lane."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
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


def main():
    rows = fetch_shadow_predictions(limit=10000)
    report = build_runner_report(rows)
    summary_path = os.getenv("RESEARCH_ADAPTIVE_ACCURACY_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

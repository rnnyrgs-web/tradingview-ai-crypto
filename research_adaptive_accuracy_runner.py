"""Heavy research-only runner for the adaptive accuracy experiment lane."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import fetch_shadow_predictions
from research_adaptive_accuracy import build_adaptive_accuracy_report
from research_learning_state import append_lesson, load_state


def build_runner_report(rows):
    memory = load_state()
    report = build_adaptive_accuracy_report(rows, memory)
    lesson = report.get("memory_lesson")
    if isinstance(lesson, dict):
        append_lesson(lesson)
        refreshed = load_state()
        report["research_memory"] = {
            "lesson_count": len(refreshed.get("lessons") or []),
            "updated_at": refreshed.get("updated_at"),
        }
    else:
        report["research_memory"] = {
            "lesson_count": len(memory.get("lessons") or []),
            "updated_at": memory.get("updated_at"),
        }
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

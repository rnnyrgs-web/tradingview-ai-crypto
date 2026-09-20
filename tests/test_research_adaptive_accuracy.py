from datetime import datetime, timedelta, timezone

from research_adaptive_accuracy import (
    _lesson_fingerprint,
    _materially_more_evidence,
    _passes_validation,
    build_adaptive_accuracy_report,
)
from research_quant_science_factory import _scientific_design


def _rows(horizon="24h", count=90, *, start=None, validation_helpful=True):
    span = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    start = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for idx in range(count):
        origin = start + span * idx
        due = origin + span
        # Development deliberately contains a bad 70-79 group so the factory
        # can discover it without seeing validation/OOS outcomes.
        dev = idx < int(count * 0.60)
        group_bad = idx % 2 == 0
        if dev:
            correct = not group_bad
        elif validation_helpful:
            correct = not group_bad
        else:
            correct = idx % 4 in {0, 1}
        score = 75 if group_bad else 85
        directional_return = 1.0 if correct else -1.0
        rows.append(
            {
                "horizon": horizon,
                "due_at": due.isoformat(),
                "resolved_at": due.isoformat(),
                "correct": correct,
                "score": score,
                "direction": "BUY",
                "market_regime": "TREND",
                "strategy_identity": "strategy-a",
                "directional_return_pct": directional_return,
            }
        )
    return rows


def _dataset(validation_helpful=True):
    # Keep horizon calendars separated so global diagnostic independence is
    # deterministic and does not accidentally overlap 24h and 7d windows.
    return _rows("24h", 90, start=datetime(2024, 1, 1, tzinfo=timezone.utc), validation_helpful=validation_helpful) + _rows(
        "7d", 90, start=datetime(2019, 1, 1, tzinfo=timezone.utc), validation_helpful=validation_helpful
    )


def test_validation_must_pass_before_untouched_oos_is_opened():
    report = build_adaptive_accuracy_report(_dataset(validation_helpful=True), {"lessons": []})
    assert report["experiment"] is not None
    assert report["experiment"]["validation_passed"] is True
    assert report["oos_opened"] is True
    assert report["experiment"]["untouched_oos"] is not None
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False


def test_failed_validation_keeps_untouched_oos_sealed():
    report = build_adaptive_accuracy_report(_dataset(validation_helpful=False), {"lessons": []})
    assert report["experiment"] is not None
    assert report["experiment"]["validation_passed"] is False
    assert report["oos_opened"] is False
    assert report["experiment"]["untouched_oos"] is None
    assert report["evidence_conclusion"] == "validation_failed"
    assert report["memory_lesson"]["reason_not_to_repeat"]


def test_validation_gate_rejects_forged_thresholds_but_accepts_canonical_design():
    evaluation = {
        "baseline": {"precision": 0.5},
        "filtered": {
            "samples": 8,
            "after_cost_expectancy_pct": 0.1,
            "precision_multiple_testing_lower": 0.6,
            "expectancy_sample_complete": True,
        },
        "precision_lift": 0.02,
        "actionable_coverage": 0.25,
    }
    canonical = _scientific_design(
        {"dimension": "market_regime", "group": "TREND", "target_horizon": "both"}
    )
    assert _passes_validation(evaluation, canonical) is True

    forged = dict(canonical)
    forged["minimum_effect_to_continue"] = {
        "precision_absolute_improvement": -1.0,
        "after_cost_expectancy_must_be_positive": True,
    }
    forged["minimum_evaluation_samples"] = 1
    forged["minimum_actionable_coverage"] = 0.001
    assert _passes_validation(
        {
            **evaluation,
            "filtered": {**evaluation["filtered"], "samples": 1},
            "precision_lift": 0.0,
            "actionable_coverage": 0.01,
        },
        forged,
    ) is False


def test_insufficient_resolved_history_fails_closed_without_dispatch():
    report = build_adaptive_accuracy_report(_rows("24h", 8), {"lessons": []})
    assert report["experiment"] is None
    assert report["oos_opened"] is False
    assert report["evidence_conclusion"] == "no_dispatchable_hypothesis"


def test_conclusive_memory_requires_materially_more_evidence_before_repeat():
    lesson = {
        "fingerprint": _lesson_fingerprint("score_band", "70-79"),
        "outcome": "validation_failed",
        "evidence_summary": {"independent_samples_at_test": 20},
    }
    assert _materially_more_evidence(23, lesson) is False
    assert _materially_more_evidence(25, lesson) is True

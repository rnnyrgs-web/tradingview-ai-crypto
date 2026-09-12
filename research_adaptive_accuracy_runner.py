"""Heavy research-only runner for the adaptive accuracy experiment lane."""

from __future__ import annotations

import json
import os
from pathlib import Path

from db import configured as prediction_ledger_configured, fetch_shadow_predictions
from ffrizz_secondary_runner import run as run_ffrizz_secondary
from research_adaptive_accuracy import build_adaptive_accuracy_report
from research_learning_state import append_lesson, load_state


_FFRIZZ_PERSISTENCE_PREFIX = "Supabase prediction ledger insert failed:"
_FFRIZZ_ERROR_STAGES = {"prediction_ledger_persistence", "ffrizz_collection_or_scoring"}
_FFRIZZ_HTTP_STATUS_CLASSES = {"http_4xx", "http_5xx", "http_other"}


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


def _nonnegative_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _bounded_ffrizz_failure(exc):
    """Classify a FFriZz failure without exposing response bodies or arbitrary text."""
    stage = "ffrizz_collection_or_scoring"
    status_class = None
    if isinstance(exc, RuntimeError):
        message = str(exc)
        if message.startswith(_FFRIZZ_PERSISTENCE_PREFIX):
            stage = "prediction_ledger_persistence"
            suffix = message[len(_FFRIZZ_PERSISTENCE_PREFIX):].strip()
            token = suffix.split(maxsplit=1)[0] if suffix else ""
            try:
                status = int(token)
            except (TypeError, ValueError):
                status = None
            if status is not None:
                if 400 <= status < 500:
                    status_class = "http_4xx"
                elif 500 <= status < 600:
                    status_class = "http_5xx"
                else:
                    status_class = "http_other"
    return {
        "error_type": type(exc).__name__,
        "error_stage": stage if stage in _FFRIZZ_ERROR_STAGES else "ffrizz_collection_or_scoring",
        "http_status_class": status_class if status_class in _FFRIZZ_HTTP_STATUS_CLASSES else None,
    }


def _bounded_abstention_diagnostics(value):
    """Keep only small deterministic counts from FFriZz abstention diagnostics."""
    if not isinstance(value, dict):
        return None

    def bounded_counts(raw, allowed_keys=None, max_items=24):
        if not isinstance(raw, dict):
            return {}
        output = {}
        for key, count in raw.items():
            if len(output) >= max_items:
                break
            if not isinstance(key, str) or not key:
                continue
            if allowed_keys is not None and key not in allowed_keys:
                continue
            clean = _nonnegative_int(count)
            if clean is not None:
                output[key] = clean
        return dict(sorted(output.items()))

    actions = bounded_counts(value.get("action_counts"), {"WAIT", "SHADOW_BUY", "SHADOW_SELL"}, 3)
    wait_gates = bounded_counts(
        value.get("wait_gate_counts"),
        {"insufficient_directional_agreement", "score_below_predeclared_threshold", "unexpected_wait_state"},
        3,
    )
    unavailable = bounded_counts(value.get("family_unavailable_counts"), max_items=16)
    family_distribution = bounded_counts(value.get("available_family_count_distribution"), max_items=8)
    horizon_counts = {}
    raw_horizons = value.get("horizon_counts")
    if isinstance(raw_horizons, dict):
        for horizon in ("6h", "12h", "24h", "48h", "72h", "7d"):
            row = raw_horizons.get(horizon)
            if not isinstance(row, dict):
                continue
            horizon_counts[horizon] = bounded_counts(row, {"scored", "WAIT", "SHADOW_BUY", "SHADOW_SELL"}, 4)

    return {
        "diagnostic_only": value.get("diagnostic_only") is True,
        "thresholds_unchanged": value.get("thresholds_unchanged") is True,
        "backfill_used": value.get("backfill_used") is True,
        "signals_scored": _nonnegative_int(value.get("signals_scored")),
        "action_counts": actions,
        "wait_gate_counts": wait_gates,
        "family_unavailable_counts": unavailable,
        "available_family_count_distribution": family_distribution,
        "horizon_counts": horizon_counts,
        "trade_authority": False,
        "promotion_authority": False,
    }


def _bounded_oi_source_diagnostics(value):
    """Keep only count-level OI acquisition outcomes from the existing requests."""
    if not isinstance(value, dict):
        return None
    allowed = (
        "available",
        "valid_empty",
        "http_error",
        "http_451",
        "http_429",
        "http_other_4xx",
        "http_5xx",
        "http_other",
        "timeout",
        "network_error",
        "invalid_payload",
        "source_error",
        "unclassified",
    )
    raw = value.get("status_counts") if isinstance(value.get("status_counts"), dict) else {}
    counts = {
        key: clean
        for key in allowed
        if (clean := _nonnegative_int(raw.get(key))) is not None
    }
    return {
        "diagnostic_only": value.get("diagnostic_only") is True,
        "source": "binance_open_interest_history",
        "acquisition_attempts": _nonnegative_int(value.get("acquisition_attempts")),
        "status_counts": counts,
        "extra_requests_added": 0,
        "symbol_level_data_exposed": False,
        "trade_authority": False,
        "promotion_authority": False,
    }


def _bounded_feature_availability(value, *, system, oi_family, include_reasons=False):
    """Keep only predeclared horizon/family counts from an OI challenger."""
    if not isinstance(value, dict):
        return None
    allowed_families = {
        "pb_ema:available",
        "pb_ema:unavailable",
        "fvg:available",
        "fvg:unavailable",
        "inside_bar:available",
        "inside_bar:unavailable",
        f"{oi_family}:available",
        f"{oi_family}:unavailable",
    }
    allowed_reasons = {
        "oi_unavailable",
        "unsupported_bar",
        "ambiguous_duplicate_candle_close",
        "price_unavailable",
        "ambiguous_duplicate_oi_period_end",
        "ambiguous_reused_price_endpoint",
        "insufficient_causal_asof_overlap",
        "correlation_undefined",
    }
    horizons = {}
    raw_horizons = value.get("horizons")
    if isinstance(raw_horizons, dict):
        for horizon in ("6h", "12h", "24h"):
            row = raw_horizons.get(horizon)
            if not isinstance(row, dict):
                continue
            counts = row.get("family_counts") if isinstance(row.get("family_counts"), dict) else {}
            clean_counts = {}
            for key in sorted(allowed_families):
                clean = _nonnegative_int(counts.get(key))
                if clean is not None:
                    clean_counts[key] = clean
            bounded = {
                "signals_scored": _nonnegative_int(row.get("signals_scored")),
                "family_counts": clean_counts,
            }
            if include_reasons:
                reasons = row.get("oi_unavailable_reason_counts") if isinstance(row.get("oi_unavailable_reason_counts"), dict) else {}
                bounded["oi_unavailable_reason_counts"] = {
                    reason: clean
                    for reason in sorted(allowed_reasons)
                    if (clean := _nonnegative_int(reasons.get(reason))) is not None
                }
            horizons[horizon] = bounded
    return {
        "system": system,
        "diagnostic_only": value.get("diagnostic_only") is True,
        "symbol_level_data_exposed": False,
        "horizons": horizons,
        "trade_authority": False,
        "promotion_authority": False,
    }


def _bounded_v2_feature_availability(value):
    return _bounded_feature_availability(
        value,
        system="FFRIZZ_SECONDARY_V2_OI_CLOSE_END",
        oi_family="price_oi_correlation_v2",
    )


def _bounded_v3_feature_availability(value):
    bounded = _bounded_feature_availability(
        value,
        system="FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF",
        oi_family="price_oi_correlation_v3",
        include_reasons=True,
    )
    if bounded is None:
        return None
    bounded.update({
        "causal_asof_only": True,
        "future_price_used": False,
        "nearest_neighbor_used": False,
        "interpolation_used": False,
        "max_price_staleness_ms_exclusive": 3_600_000,
    })
    return bounded


def _ffrizz_forward_collection():
    """Collect FFriZz forward evidence inside the already-bounded heavy lane.

    This deliberately does not create another worker, Render service, concurrency
    slot, or production authority. A generated eligible forecast is not reported
    as successfully collected unless the canonical prediction-ledger connection is
    configured; otherwise db.insert_prediction_ledger would intentionally no-op and
    observability could falsely report collection success while preserving no row.
    """
    try:
        report = run_ffrizz_secondary(persist=True)
    except Exception as exc:
        return {
            "ok": False,
            "research_only": True,
            **_bounded_ffrizz_failure(exc),
            "trade_authority": False,
            "promotion_authority": False,
        }
    forward = report.get("forward_evidence") if isinstance(report, dict) else {}
    eligible = int((forward or {}).get("eligible_shadow_forecasts") or 0)
    abstention = _bounded_abstention_diagnostics((forward or {}).get("abstention_diagnostics"))
    oi_source = _bounded_oi_source_diagnostics(report.get("oi_source_diagnostics") if isinstance(report, dict) else None)
    v2_availability = _bounded_v2_feature_availability(
        report.get("v2_oi_alignment_feature_availability") if isinstance(report, dict) else None
    )
    v3_availability = _bounded_v3_feature_availability(
        report.get("v3_oi_causal_asof_feature_availability") if isinstance(report, dict) else None
    )
    common = {
        "research_only": True,
        "system": report.get("system"),
        "generated_at": report.get("generated_at"),
        "eligible_shadow_forecasts": eligible,
        "non_overlapping_full_horizon_buckets": (forward or {}).get("non_overlapping_full_horizon_buckets") is True,
        "wait_rows_persisted": (forward or {}).get("wait_rows_persisted") is True,
        "historical_oi_backfill_used": (forward or {}).get("historical_oi_backfill_used") is True,
        "abstention_diagnostics": abstention,
        "oi_source_diagnostics": oi_source,
        "v2_oi_alignment_feature_availability": v2_availability,
        "v3_oi_causal_asof_feature_availability": v3_availability,
        "trade_authority": False,
        "promotion_authority": False,
    }
    if eligible > 0 and not prediction_ledger_configured():
        return {
            **common,
            "ok": False,
            "error_type": "PredictionLedgerNotConfigured",
            "error_stage": "prediction_ledger_configuration",
            "http_status_class": None,
        }
    return {
        **common,
        "ok": True,
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
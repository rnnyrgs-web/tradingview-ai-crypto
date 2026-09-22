from __future__ import annotations

import copy
import gzip
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from btc_leadlag_selection import DATASET_PATH
from orchestration.external_replication.abnormal_day_momentum_runner import (
    DataPitInconclusiveError,
    ScoredEvent,
    build_signal_schedule,
    schedule_as_dicts,
    score_schedule,
    split_by_period,
    summarize,
)
from research_artifact import sha256_hex
from strategy_dataset_preflight import (
    DEVELOPMENT_END_UTC,
    PROTECTED_START_UTC,
    _git_blob_sha1,
    _parse_development_view,
    _parse_hour,
    qualify_cohort001_dataset,
)

ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION_PATH = ROOT / "orchestration/external_replication/ext_abnormal_day_momentum_001_v1.json"
EXECUTION_CONTRACT_PATH = ROOT / "orchestration/external_replication/ext_abnormal_day_momentum_001_stage1_execution.json"
UTC = timezone.utc


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("execution-contract timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain one JSON object")
    return value


def _validate_contracts(predecl: dict[str, Any], execution: dict[str, Any]) -> None:
    if predecl.get("replication_id") != "EXT-ABNORMAL-DAY-MOMENTUM-001-v1":
        raise RuntimeError("unexpected replication predeclaration")
    unsigned = copy.deepcopy(predecl)
    expected_digest = unsigned.pop("artifact_sha256", None)
    if not isinstance(expected_digest, str) or sha256_hex(unsigned) != expected_digest:
        raise RuntimeError("replication predeclaration digest mismatch")
    if execution.get("execution_contract_id") != "EXT-ABNORMAL-DAY-MOMENTUM-001-v1-STAGE1":
        raise RuntimeError("unexpected Stage-1 execution contract")
    if execution.get("replication_id") != predecl["replication_id"]:
        raise RuntimeError("execution contract is not bound to replication predeclaration")
    if execution.get("formed_before_outcomes") is not True:
        raise RuntimeError("Stage-1 execution semantics were not frozen before outcomes")
    if execution["authority"] != {
        "research_only": True,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
    }:
        raise RuntimeError("Stage-1 execution authority must remain research-only")

    data = predecl["data_contract"]
    frozen_data = execution["dataset_contract"]
    if frozen_data["normalized_rows_sha256"] != data["normalized_rows_sha256"]:
        raise RuntimeError("execution contract dataset identity mismatch")
    if frozen_data["development_end_utc"] != data["selection_validation_end_utc"]:
        raise RuntimeError("execution contract development cutoff mismatch")
    if frozen_data["protected_oos_start_utc"] != data["protected_oos_start_utc"]:
        raise RuntimeError("execution contract protected boundary mismatch")
    if frozen_data["protected_ohlcv_may_be_decoded"] is not False:
        raise RuntimeError("protected OHLCV must remain closed")

    screen = execution["screen"]
    rules = predecl["signal_rules"]
    costs = predecl["cost_model"]
    if screen != {
        "parameter_variants": 1,
        "reference_days": rules["reference_window_completed_utc_days"],
        "sigma_multiple": rules["abnormal_sigma_multiple"],
        "latest_signal_hour_utc": rules["latest_signal_hour_utc"],
        "base_total_cost_bps": costs["base_total_bps"],
        "middle_cost_multiplier": 2.0,
        "stress_multiplier": 3.0,
        "independent_sample_unit": "unique_utc_signal_day_pooled_across_fixed_instruments",
    }:
        raise RuntimeError("Stage-1 screen parameters drifted from the frozen one-variant design")
    frozen_cost_multipliers = [float(value) for value in costs["stress_multipliers"]]
    if 2.0 not in frozen_cost_multipliers or 3.0 not in frozen_cost_multipliers:
        raise RuntimeError("2x and 3x cost stresses must both be predeclared")

    sizing = execution.get("portfolio_sizing")
    expected_instruments = list(data["fixed_instruments"])
    if sizing != {
        "fixed_instruments": expected_instruments,
        "nav_fraction_per_eligible_instrument": 1.0 / len(expected_instruments),
        "max_simultaneous_positions": len(expected_instruments),
        "max_gross_nav_fraction": 1.0,
        "sizing_decision": "fixed_per_instrument_before_later_same_day_signals",
        "final_same_day_signal_count_normalization_allowed": False,
        "authoritative_economic_unit": "nav_weighted_unique_utc_signal_day_portfolio_block",
        "controls_use_same_sizing_and_aggregation": True,
    }:
        raise RuntimeError("Stage-1 portfolio sizing/aggregation contract drifted")
    if len(expected_instruments) != 3 or len(set(expected_instruments)) != 3:
        raise RuntimeError("replication sizing contract requires exactly three fixed instruments")

    gates = execution.get("stage1_gates")
    if not isinstance(gates, dict):
        raise RuntimeError("Stage-1 gates must be an object")
    predecl_gates = predecl["cheap_stage_gates"]
    if gates.get("minimum_independent_utc_signal_days_train") != predecl_gates[
        "minimum_independent_trades_train"
    ]:
        raise RuntimeError("train independent-day gate drifted from predeclaration")
    if gates.get("minimum_independent_utc_signal_days_validation") != predecl_gates[
        "minimum_independent_trades_validation"
    ]:
        raise RuntimeError("validation independent-day gate drifted from predeclaration")
    if gates.get("train_profit_factor_gt") != 1.0 or gates.get("validation_profit_factor_gt") != 1.0:
        raise RuntimeError("profit-factor threshold must remain strictly above one")
    if gates.get("single_winner_dependence_veto") != (
        "leave_largest_positive_independent_utc_signal_day_block_out_total_must_be_positive_in_train_and_validation"
    ):
        raise RuntimeError("single-winner veto must use the frozen independent UTC-day block")
    if gates.get("catastrophic_tail_veto") != (
        "repeat_worst_independent_utc_signal_day_block_once_more_total_must_be_positive_in_train_and_validation"
    ):
        raise RuntimeError("catastrophic-tail veto must use the frozen independent UTC-day block")


def _load_development_rows(dataset_path: Path) -> tuple[list[dict[str, object]], dict[str, Any]]:
    qualification = qualify_cohort001_dataset(dataset_path)
    if qualification["status"] != "QUALIFIED_DEVELOPMENT_ONLY":
        raise RuntimeError("dataset is not qualified for development-only screening")
    checks = qualification["checks"]
    if checks.get("protected_ohlcv_json_decoded") is not False:
        raise RuntimeError("protected OHLCV was decoded during qualification")
    if qualification.get("untouched_oos_opened") is not False:
        raise RuntimeError("protected OOS was opened during qualification")

    compressed = dataset_path.read_bytes()
    if _git_blob_sha1(compressed) != qualification["source_git_blob_sha1"]:
        raise RuntimeError("dataset bytes changed after protected-safe qualification")
    uncompressed = gzip.decompress(compressed)
    cutoff = _parse_hour(DEVELOPMENT_END_UTC)
    protected = _parse_hour(PROTECTED_START_UTC)
    metadata, development_histories, _source_timestamps = _parse_development_view(
        uncompressed,
        cutoff_ms=int(cutoff.timestamp() * 1000),
        protected_ms=int(protected.timestamp() * 1000),
    )
    if metadata.get("bar") != "1H":
        raise RuntimeError("unexpected development bar interval")

    rows: list[dict[str, object]] = []
    for instrument in qualification["instruments"]:
        history = development_histories.get(instrument)
        if history is None:
            raise RuntimeError(f"qualified instrument missing from development view: {instrument}")
        for row in history:
            ts = datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC)
            if ts >= protected:
                raise RuntimeError("protected market row entered Stage-1 adapter")
            rows.append(
                {
                    "instrument": instrument,
                    "timestamp": ts,
                    "open": float(row["open"]),
                    "close": float(row["close"]),
                }
            )
    return rows, qualification


def _json_safe_number(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _profit_factor(values: list[float]) -> float | None:
    gains = [value for value in values if value > 0]
    losses = [-value for value in values if value < 0]
    if losses:
        return sum(gains) / sum(losses)
    if gains:
        return float("inf")
    return None


def _portfolio_summary(
    scored: Iterable[ScoredEvent],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Authoritative Stage-1 economics on frozen NAV-weighted UTC-day blocks.

    Raw asset-event returns remain diagnostics only. Every eligible instrument is
    sized at the same fixed NAV fraction before any later same-day signal can be
    known, so a one-signal day uses one-third NAV while a three-signal day uses
    at most one full NAV. We never normalize by the final same-day signal count.
    """

    events = tuple(scored)
    sizing = execution["portfolio_sizing"]
    allowed = tuple(sizing["fixed_instruments"])
    allowed_set = set(allowed)
    weight = float(sizing["nav_fraction_per_eligible_instrument"])
    max_positions = int(sizing["max_simultaneous_positions"])
    max_gross = float(sizing["max_gross_nav_fraction"])
    base_cost_bps = float(execution["screen"]["base_total_cost_bps"])
    middle_multiplier = float(execution["screen"]["middle_cost_multiplier"])
    middle_cost = base_cost_bps * middle_multiplier / 10_000.0

    daily: dict[object, dict[str, Any]] = {}
    for event in events:
        instrument = event.signal.instrument
        if instrument not in allowed_set:
            raise RuntimeError(f"scored event outside frozen instrument set: {instrument}")
        day = event.signal.signal_timestamp.astimezone(UTC).date()
        bucket = daily.setdefault(
            day,
            {
                "instruments": set(),
                "base": 0.0,
                "middle": 0.0,
                "stress": 0.0,
            },
        )
        instruments = bucket["instruments"]
        if instrument in instruments:
            raise RuntimeError("duplicate instrument on one authoritative UTC signal-day block")
        instruments.add(instrument)
        if len(instruments) > max_positions or len(instruments) * weight > max_gross + 1e-12:
            raise RuntimeError("authoritative UTC signal-day block exceeds frozen gross-position cap")
        bucket["base"] += weight * event.net_return
        bucket["middle"] += weight * (event.gross_return - middle_cost)
        bucket["stress"] += weight * event.stress_3x_net_return

    ordered = sorted(daily.items(), key=lambda item: item[0])
    base_blocks = [float(bucket["base"]) for _, bucket in ordered]
    middle_blocks = [float(bucket["middle"]) for _, bucket in ordered]
    stress_blocks = [float(bucket["stress"]) for _, bucket in ordered]
    total = sum(base_blocks)
    largest_positive = max((value for value in base_blocks if value > 0), default=0.0)
    worst = min(base_blocks, default=0.0)
    positive_total = sum(value for value in base_blocks if value > 0)
    winner_concentration = largest_positive / positive_total if positive_total > 0 else None

    raw = summarize(events)
    raw_diagnostics = {key: _json_safe_number(value) for key, value in raw.items()}
    pf = _profit_factor(base_blocks)

    return {
        "n": len(base_blocks),
        "raw_event_count": len(events),
        "independent_utc_signal_days": len(base_blocks),
        "independent_utc_signal_day_blocks": len(base_blocks),
        "mean_net_return": mean(base_blocks) if base_blocks else None,
        "total_net_return": total,
        "profit_factor": _json_safe_number(pf),
        "total_2x_cost_return": sum(middle_blocks),
        "total_3x_cost_return": sum(stress_blocks),
        "largest_positive_independent_day_block_return": largest_positive,
        "winner_concentration_share_of_positive_day_blocks": winner_concentration,
        "leave_largest_independent_day_block_out_total": total - largest_positive,
        "worst_independent_day_block_return": worst,
        "repeat_worst_independent_day_block_total": total + worst,
        "portfolio_sizing": {
            "nav_fraction_per_eligible_instrument": weight,
            "max_simultaneous_positions": max_positions,
            "max_gross_nav_fraction": max_gross,
            "final_same_day_signal_count_normalization_allowed": False,
        },
        "raw_event_diagnostics_non_authoritative": raw_diagnostics,
    }


def _positive_profit_factor(summary: dict[str, Any], threshold: float) -> bool:
    value = summary["profit_factor"]
    return value == "Infinity" or (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > threshold
    )


def _subset_by_signal_time(
    scored: Iterable[ScoredEvent], *, start: datetime, end: datetime
) -> tuple[ScoredEvent, ...]:
    return tuple(
        event
        for event in scored
        if start <= event.signal.signal_timestamp.astimezone(UTC) <= end
    )


def evaluate_stage1_gates(
    train: tuple[ScoredEvent, ...],
    validation: tuple[ScoredEvent, ...],
    execution: dict[str, Any],
) -> tuple[str, dict[str, bool], dict[str, dict[str, Any]]]:
    halves = execution["validation_halves"]
    first = _subset_by_signal_time(
        validation,
        start=_parse_utc(halves["first_start_utc"]),
        end=_parse_utc(halves["first_end_utc"]),
    )
    second = _subset_by_signal_time(
        validation,
        start=_parse_utc(halves["second_start_utc"]),
        end=_parse_utc(halves["second_end_utc"]),
    )
    if len(first) + len(second) != len(validation):
        raise RuntimeError("validation-half contract does not partition all validation events")

    summaries = {
        "train": _portfolio_summary(train, execution),
        "validation": _portfolio_summary(validation, execution),
        "validation_first_half": _portfolio_summary(first, execution),
        "validation_second_half": _portfolio_summary(second, execution),
    }
    gates = execution["stage1_gates"]
    train_summary = summaries["train"]
    validation_summary = summaries["validation"]
    gate_results = {
        "minimum_independent_days_train": train_summary["independent_utc_signal_days"]
        >= gates["minimum_independent_utc_signal_days_train"],
        "minimum_independent_days_validation": validation_summary["independent_utc_signal_days"]
        >= gates["minimum_independent_utc_signal_days_validation"],
        "positive_after_cost_train": train_summary["total_net_return"]
        > gates["train_total_after_cost_return_gt"],
        "positive_after_cost_validation": validation_summary["total_net_return"]
        > gates["validation_total_after_cost_return_gt"],
        "validation_first_half_positive": summaries["validation_first_half"]["total_net_return"]
        > gates["validation_first_half_total_after_cost_return_gt"],
        "validation_second_half_positive": summaries["validation_second_half"]["total_net_return"]
        > gates["validation_second_half_total_after_cost_return_gt"],
        "profit_factor_train": _positive_profit_factor(
            train_summary, gates["train_profit_factor_gt"]
        ),
        "profit_factor_validation": _positive_profit_factor(
            validation_summary, gates["validation_profit_factor_gt"]
        ),
        "three_x_cost_positive_train": train_summary["total_3x_cost_return"]
        > gates["train_total_3x_cost_return_gt"],
        "three_x_cost_positive_validation": validation_summary["total_3x_cost_return"]
        > gates["validation_total_3x_cost_return_gt"],
        "single_winner_veto_train": train_summary[
            "leave_largest_independent_day_block_out_total"
        ]
        > 0.0,
        "single_winner_veto_validation": validation_summary[
            "leave_largest_independent_day_block_out_total"
        ]
        > 0.0,
        "catastrophic_tail_veto_train": train_summary[
            "repeat_worst_independent_day_block_total"
        ]
        > 0.0,
        "catastrophic_tail_veto_validation": validation_summary[
            "repeat_worst_independent_day_block_total"
        ]
        > 0.0,
    }
    if (
        not gate_results["minimum_independent_days_train"]
        or not gate_results["minimum_independent_days_validation"]
    ):
        classification = "UNDERPOWERED"
    elif all(gate_results.values()):
        classification = "STAGE1_SURVIVOR_REQUIRES_FROZEN_CONTROLS"
    else:
        classification = "STAGE1_REJECTED"
    return classification, gate_results, summaries


def run_stage1(dataset_path: Path = DATASET_PATH) -> dict[str, Any]:
    predecl = _load_json(PREDECLARATION_PATH)
    execution = _load_json(EXECUTION_CONTRACT_PATH)
    _validate_contracts(predecl, execution)
    rows, qualification = _load_development_rows(dataset_path)

    data = predecl["data_contract"]
    rules = predecl["signal_rules"]
    screen = execution["screen"]
    schedule = build_signal_schedule(
        rows,
        train_start=data["selection_train_start_utc"],
        train_end=data["selection_train_end_utc"],
        validation_start=data["selection_validation_start_utc"],
        validation_end=data["selection_validation_end_utc"],
        protected_oos_start=data["protected_oos_start_utc"],
        reference_days=screen["reference_days"],
        sigma_multiple=screen["sigma_multiple"],
        latest_signal_hour_utc=screen["latest_signal_hour_utc"],
    )
    schedule_payload = schedule_as_dicts(schedule)

    try:
        scored = score_schedule(
            rows,
            schedule,
            protected_oos_start=data["protected_oos_start_utc"],
            base_cost_bps=screen["base_total_cost_bps"],
            stress_multiplier=screen["stress_multiplier"],
            direction_source="candidate",
            entry_delay_bars=0,
        )
    except DataPitInconclusiveError as exc:
        result = {
            "schema_version": 1,
            "replication_id": predecl["replication_id"],
            "execution_contract_id": execution["execution_contract_id"],
            "execution_contract_sha256": sha256_hex(execution),
            "classification": "DATA/PIT_INCONCLUSIVE",
            "schedule_sha256": sha256_hex(schedule_payload),
            "scheduled_events": len(schedule_payload),
            "execution_issues": [
                {
                    "instrument": issue.instrument,
                    "period": issue.period,
                    "signal_timestamp": issue.signal_timestamp.isoformat().replace("+00:00", "Z"),
                    "required_timestamp": issue.required_timestamp.isoformat().replace("+00:00", "Z"),
                    "reason": issue.reason,
                    "entry_delay_bars": issue.entry_delay_bars,
                }
                for issue in exc.issues
            ],
            "dataset_qualification_receipt_sha256": qualification["receipt_sha256"],
            "protected_oos_opened": False,
            "genuine_forward_opened": False,
            "broker_connected": False,
            "trade_authority": False,
            "promotion_authority": False,
        }
        result["result_sha256"] = sha256_hex(result)
        return result

    periods = split_by_period(scored)
    classification, gate_results, summaries = evaluate_stage1_gates(
        periods["train"], periods["validation"], execution
    )
    result = {
        "schema_version": 1,
        "replication_id": predecl["replication_id"],
        "execution_contract_id": execution["execution_contract_id"],
        "execution_contract_sha256": sha256_hex(execution),
        "classification": classification,
        "schedule_sha256": sha256_hex(schedule_payload),
        "scheduled_events": len(schedule_payload),
        "scored_events": len(scored),
        "gate_results": gate_results,
        "summaries": summaries,
        "dataset_qualification_receipt_sha256": qualification["receipt_sha256"],
        "dataset_normalized_rows_sha256": data["normalized_rows_sha256"],
        "cost_semantics": {
            "base_total_bps": screen["base_total_cost_bps"],
            "middle_total_bps": screen["base_total_cost_bps"]
            * screen["middle_cost_multiplier"],
            "stress_multiplier": screen["stress_multiplier"],
            "stress_total_bps": screen["base_total_cost_bps"] * screen["stress_multiplier"],
            "authoritative_economics": "NAV-weighted UTC signal-day portfolio blocks",
        },
        "portfolio_sizing": execution["portfolio_sizing"],
        "parameter_variants": 1,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    result["result_sha256"] = sha256_hex(result)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_stage1(args.dataset)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

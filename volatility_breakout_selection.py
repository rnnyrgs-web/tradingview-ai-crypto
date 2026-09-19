"""Selection-only cheap screen for DISC-VOL-BREAKOUT-001-v1.

The scientific contract is frozen before outcome inspection. The runner uses a
fixed set of OKX USDT perpetuals, scores only train/validation evidence, keeps
the final 20% untouched OOS locked, and cannot authorize promotion or trading.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "orchestration" / "disc_vol_breakout_001.json"

LOCKED_OOS = {
    "status": "LOCKED_UNTOUCHED_OOS",
    "reason": "selection-only cheap screen; central freeze is required before untouched-OOS access",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = contract.get("contract_sha256")
    definition = contract.get("contract_fingerprint_definition")
    payload = dict(contract)
    payload.pop("contract_sha256", None)
    payload.pop("contract_fingerprint_definition", None)
    if not isinstance(fingerprint, str) or not fingerprint:
        raise RuntimeError("selection contract is missing contract_sha256")
    if not isinstance(definition, str) or not definition:
        raise RuntimeError("selection contract is missing fingerprint definition")
    if _sha256_hex(payload) != fingerprint:
        raise RuntimeError("selection contract fingerprint mismatch")
    if contract.get("fingerprint_id") != "DISC-VOL-BREAKOUT-001-v1":
        raise RuntimeError("unexpected volatility-breakout fingerprint")
    if contract.get("chronology", {}).get("untouched_oos") != "LOCKED":
        raise RuntimeError("selection contract must keep untouched OOS locked")
    source = contract.get("source", {})
    if source.get("asset_substitution_allowed") is not False:
        raise RuntimeError("fixed-asset contract cannot allow outcome-driven asset substitution")
    if contract.get("search_breadth", {}).get("parameter_optimization_allowed") is not False:
        raise RuntimeError("selection contract cannot permit parameter optimization")
    return contract


def _validate_rows(rows: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    normalized: list[dict[str, float | int]] = []
    previous_ts: int | None = None
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("history row must be an object")
        try:
            ts = int(raw["ts"])
            o = float(raw["open"])
            h = float(raw["high"])
            l = float(raw["low"])
            c = float(raw["close"])
            v = float(raw.get("volume", 0.0))
            qv = float(raw.get("quote_volume", 0.0))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("history row contains malformed values") from exc
        numeric = (o, h, l, c, v, qv)
        if ts <= 0 or not all(math.isfinite(x) for x in numeric):
            raise ValueError("history row contains non-finite or invalid timestamp")
        if min(o, h, l, c) <= 0 or v < 0 or qv < 0:
            raise ValueError("history row contains impossible market values")
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("history OHLC ordering is impossible")
        if previous_ts is not None and ts <= previous_ts:
            raise ValueError("history must be strictly chronological and duplicate-free")
        previous_ts = ts
        normalized.append(
            {
                "ts": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "quote_volume": qv,
            }
        )
    return normalized


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of empty data")
    if not (0.0 <= q <= 1.0):
        raise ValueError("percentile q must be in [0,1]")
    ordered = sorted(float(x) for x in values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _atr(rows: list[dict[str, float | int]], window: int) -> list[float | None]:
    if window < 2:
        raise ValueError("ATR window must be >=2")
    tr: list[float] = []
    for i, row in enumerate(rows):
        h = float(row["high"])
        l = float(row["low"])
        if i == 0:
            tr.append(h - l)
        else:
            prev_close = float(rows[i - 1]["close"])
            tr.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
    out: list[float | None] = [None] * len(rows)
    running = 0.0
    for i, value in enumerate(tr):
        running += value
        if i >= window:
            running -= tr[i - window]
        if i >= window - 1:
            out[i] = running / window
    return out


def _compression_flags(
    rows: list[dict[str, float | int]],
    atr_values: list[float | None],
    *,
    reference_window: int,
    quantile: float,
) -> list[bool]:
    ratios: list[float | None] = []
    for i, atr_value in enumerate(atr_values):
        close = float(rows[i]["close"])
        ratios.append(None if atr_value is None or close <= 0 else float(atr_value) / close)
    flags = [False] * len(rows)
    for i, current in enumerate(ratios):
        if current is None or i < reference_window:
            continue
        prior = [x for x in ratios[i - reference_window : i] if x is not None]
        if len(prior) != reference_window:
            continue
        flags[i] = current <= _percentile([float(x) for x in prior], quantile)
    return flags


def _regime(rows: list[dict[str, float | int]], signal_index: int, window: int = 168) -> str:
    start = signal_index - window + 1
    if start < 0:
        return "UNKNOWN"
    closes = [float(row["close"]) for row in rows[start : signal_index + 1]]
    mean = sum(closes) / len(closes)
    return "BULL" if float(rows[signal_index]["close"]) >= mean else "BEAR"


def _exit_trade(
    rows: list[dict[str, float | int]],
    *,
    signal_index: int,
    direction: int,
    signal_atr: float,
    stop_multiple: float,
    target_multiple: float,
    max_hold_bars: int,
    segment_end: int,
) -> dict[str, Any] | None:
    entry_index = signal_index + 1
    time_exit_index = entry_index + max_hold_bars
    if time_exit_index >= segment_end:
        return None
    entry = float(rows[entry_index]["open"])
    distance = signal_atr
    if not math.isfinite(distance) or distance <= 0 or entry <= 0:
        return None

    if direction > 0:
        stop = entry - stop_multiple * distance
        target = entry + target_multiple * distance
    else:
        stop = entry + stop_multiple * distance
        target = entry - target_multiple * distance
    if stop <= 0 or target <= 0:
        return None

    exit_index: int | None = None
    exit_price: float | None = None
    exit_reason = "TIME"
    for idx in range(entry_index, time_exit_index):
        row = rows[idx]
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        if direction > 0:
            if o <= stop:
                exit_index, exit_price, exit_reason = idx, o, "STOP_GAP"
                break
            if o >= target:
                exit_index, exit_price, exit_reason = idx, target, "TARGET_GAP_CAPPED"
                break
            stop_hit = l <= stop
            target_hit = h >= target
            if stop_hit:
                exit_index, exit_price, exit_reason = idx, stop, "STOP"
                break
            if target_hit:
                exit_index, exit_price, exit_reason = idx, target, "TARGET"
                break
        else:
            if o >= stop:
                exit_index, exit_price, exit_reason = idx, o, "STOP_GAP"
                break
            if o <= target:
                exit_index, exit_price, exit_reason = idx, target, "TARGET_GAP_CAPPED"
                break
            stop_hit = h >= stop
            target_hit = l <= target
            if stop_hit:
                exit_index, exit_price, exit_reason = idx, stop, "STOP"
                break
            if target_hit:
                exit_index, exit_price, exit_reason = idx, target, "TARGET"
                break

    if exit_index is None:
        exit_index = time_exit_index
        exit_price = float(rows[time_exit_index]["open"])
    assert exit_price is not None

    gross_bps = direction * (exit_price / entry - 1.0) * 10000.0
    return {
        "signal_index": signal_index,
        "signal_ts": int(rows[signal_index]["ts"]),
        "entry_index": entry_index,
        "entry_ts": int(rows[entry_index]["ts"]),
        "exit_index": exit_index,
        "exit_ts": int(rows[exit_index]["ts"]),
        "direction": "LONG" if direction > 0 else "SHORT",
        "regime": _regime(rows, signal_index),
        "entry_price": entry,
        "exit_price": exit_price,
        "gross_bps": gross_bps,
        "exit_reason": exit_reason,
    }


def _generate_trades(
    rows: list[dict[str, float | int]],
    *,
    start_index: int,
    end_index: int,
    contract: dict[str, Any],
    compression_quantile: float | None,
) -> list[dict[str, Any]]:
    rule = contract["primary_rule"]
    atr_window = int(rule["atr_window_bars"])
    reference_window = int(rule["compression_reference_window_bars"])
    recency = int(rule["compression_recency_bars"])
    breakout_window = int(rule["breakout_window_bars"])
    stop_multiple = float(rule["stop_atr_multiple"])
    target_multiple = float(rule["target_atr_multiple"])
    max_hold = int(rule["maximum_hold_bars"])
    warmup = int(contract["chronology"]["minimum_warmup_bars"])

    atr_values = _atr(rows, atr_window)
    compression = (
        None
        if compression_quantile is None
        else _compression_flags(
            rows,
            atr_values,
            reference_window=reference_window,
            quantile=float(compression_quantile),
        )
    )

    trades: list[dict[str, Any]] = []
    i = max(start_index, warmup, breakout_window, reference_window + atr_window)
    while i < end_index:
        if i + 1 + max_hold >= end_index:
            break
        atr_value = atr_values[i]
        if atr_value is None or float(atr_value) <= 0:
            i += 1
            continue
        high_break = max(float(row["high"]) for row in rows[i - breakout_window : i])
        low_break = min(float(row["low"]) for row in rows[i - breakout_window : i])
        close = float(rows[i]["close"])
        direction = 1 if close > high_break else -1 if close < low_break else 0
        if direction == 0:
            i += 1
            continue
        if compression is not None and not any(compression[max(0, i - recency) : i]):
            i += 1
            continue
        trade = _exit_trade(
            rows,
            signal_index=i,
            direction=direction,
            signal_atr=float(atr_value),
            stop_multiple=stop_multiple,
            target_multiple=target_multiple,
            max_hold_bars=max_hold,
            segment_end=end_index,
        )
        if trade is None:
            i += 1
            continue
        trades.append(trade)
        i = int(trade["exit_index"]) + 1
    return trades


def _net_values(trades: list[dict[str, Any]], cost_bps: float) -> list[float]:
    return [float(trade["gross_bps"]) - cost_bps for trade in trades]


def _profit_factor(values: list[float]) -> float | None:
    wins = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    if losses == 0:
        return None if wins == 0 else float("inf")
    return wins / losses


def _max_drawdown_bps(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return abs(worst)


def _basic_metrics(trades: list[dict[str, Any]], cost_bps: float) -> dict[str, Any]:
    values = _net_values(trades, cost_bps)
    return {
        "trades": len(values),
        "mean_net_bps": (sum(values) / len(values)) if values else None,
        "median_net_bps": statistics.median(values) if values else None,
        "total_net_bps_additive": sum(values),
        "profit_factor": _profit_factor(values),
        "win_rate": (sum(x > 0 for x in values) / len(values)) if values else None,
        "max_drawdown_bps_additive": _max_drawdown_bps(values),
    }


def _stress_metrics(trades: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    costs = contract["costs"]
    base = float(costs["base_round_trip_bps"])
    result: dict[str, Any] = {}
    for multiplier in costs["stress_multipliers"]:
        m = float(multiplier)
        result[f"{m:g}x"] = {
            "round_trip_cost_bps": base * m,
            **_basic_metrics(trades, base * m),
        }
    return result


def _max_stress(metrics: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    max_multiplier = max(float(x) for x in contract["costs"]["stress_multipliers"])
    return metrics[f"{max_multiplier:g}x"]


def _split_bounds(row_count: int, contract: dict[str, Any]) -> dict[str, int]:
    purge = int(contract["chronology"]["purge_bars_each_side"])
    train_cut = int(row_count * 0.60)
    validation_cut = int(row_count * 0.80)
    train_start = 0
    train_end = train_cut - purge
    validation_start = train_cut + purge
    validation_end = validation_cut - purge
    oos_start = validation_cut
    if train_end <= 0 or validation_start >= validation_end:
        raise ValueError("history is too short for purged chronological split")
    return {
        "train_start": train_start,
        "train_end": train_end,
        "validation_start": validation_start,
        "validation_end": validation_end,
        "oos_start": oos_start,
        "oos_end": row_count,
    }


def _segment_evidence(
    rows: list[dict[str, float | int]],
    *,
    start: int,
    end: int,
    contract: dict[str, Any],
    compression_quantile: float | None,
) -> dict[str, Any]:
    trades = _generate_trades(
        rows,
        start_index=start,
        end_index=end,
        contract=contract,
        compression_quantile=compression_quantile,
    )
    midpoint = start + (end - start) // 2
    first = [trade for trade in trades if int(trade["signal_index"]) < midpoint]
    second = [trade for trade in trades if int(trade["signal_index"]) >= midpoint]
    direction = {
        side: _stress_metrics([trade for trade in trades if trade["direction"] == side], contract)
        for side in ("LONG", "SHORT")
    }
    regime = {
        state: _stress_metrics([trade for trade in trades if trade["regime"] == state], contract)
        for state in ("BULL", "BEAR")
    }
    return {
        "start_ts": int(rows[start]["ts"]),
        "end_ts": int(rows[end - 1]["ts"]),
        "cost_stress": _stress_metrics(trades, contract),
        "first_half_cost_stress": _stress_metrics(first, contract),
        "second_half_cost_stress": _stress_metrics(second, contract),
        "direction_cost_stress": direction,
        "regime_cost_stress": regime,
        "trades": trades,
    }


def _evaluate_instrument(
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    *,
    compression_quantile: float | None,
) -> dict[str, Any]:
    clean = _validate_rows(rows)
    bounds = _split_bounds(len(clean), contract)
    return {
        "row_count": len(clean),
        "bounds": bounds,
        "train": _segment_evidence(
            clean,
            start=bounds["train_start"],
            end=bounds["train_end"],
            contract=contract,
            compression_quantile=compression_quantile,
        ),
        "validation": _segment_evidence(
            clean,
            start=bounds["validation_start"],
            end=bounds["validation_end"],
            contract=contract,
            compression_quantile=compression_quantile,
        ),
        "untouched_oos": {
            **LOCKED_OOS,
            "start_ts": int(clean[bounds["oos_start"]]["ts"]),
            "end_ts": int(clean[bounds["oos_end"] - 1]["ts"]),
            "rows": bounds["oos_end"] - bounds["oos_start"],
        },
    }


def _combine_trades(evidence_by_instrument: dict[str, Any], segment: str) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for instrument, evidence in evidence_by_instrument.items():
        for trade in evidence[segment]["trades"]:
            copy = dict(trade)
            copy["instrument"] = instrument
            combined.append(copy)
    return sorted(combined, key=lambda trade: (int(trade["signal_ts"]), str(trade["instrument"])))


def _pooled_segment(
    evidence_by_instrument: dict[str, Any],
    segment: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    trades = _combine_trades(evidence_by_instrument, segment)
    segment_start_ts = min(int(evidence[segment]["start_ts"]) for evidence in evidence_by_instrument.values())
    segment_end_ts = max(int(evidence[segment]["end_ts"]) for evidence in evidence_by_instrument.values())
    midpoint_ts = segment_start_ts + (segment_end_ts - segment_start_ts) // 2
    if not trades:
        return {
            "start_ts": segment_start_ts,
            "end_ts": segment_end_ts,
            "midpoint_ts": midpoint_ts,
            "cost_stress": _stress_metrics([], contract),
            "first_half_cost_stress": _stress_metrics([], contract),
            "second_half_cost_stress": _stress_metrics([], contract),
            "regime_cost_stress": {
                "BULL": _stress_metrics([], contract),
                "BEAR": _stress_metrics([], contract),
            },
            "direction_cost_stress": {
                "LONG": _stress_metrics([], contract),
                "SHORT": _stress_metrics([], contract),
            },
        }
    first = [trade for trade in trades if int(trade["signal_ts"]) < midpoint_ts]
    second = [trade for trade in trades if int(trade["signal_ts"]) >= midpoint_ts]
    return {
        "start_ts": segment_start_ts,
        "end_ts": segment_end_ts,
        "midpoint_ts": midpoint_ts,
        "cost_stress": _stress_metrics(trades, contract),
        "first_half_cost_stress": _stress_metrics(first, contract),
        "second_half_cost_stress": _stress_metrics(second, contract),
        "regime_cost_stress": {
            state: _stress_metrics([trade for trade in trades if trade["regime"] == state], contract)
            for state in ("BULL", "BEAR")
        },
        "direction_cost_stress": {
            side: _stress_metrics([trade for trade in trades if trade["direction"] == side], contract)
            for side in ("LONG", "SHORT")
        },
    }


def _instrument_primary_pass(primary: dict[str, Any], baseline: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    train = _max_stress(primary["train"]["cost_stress"], contract)
    validation = _max_stress(primary["validation"]["cost_stress"], contract)
    baseline_validation = _max_stress(baseline["validation"]["cost_stress"], contract)
    if train["trades"] < 20:
        reasons.append("TRAIN_SAMPLE_FLOOR")
    if validation["trades"] < 8:
        reasons.append("VALIDATION_SAMPLE_FLOOR")
    if train["mean_net_bps"] is None or train["mean_net_bps"] <= 0:
        reasons.append("TRAIN_EXPECTANCY")
    if validation["mean_net_bps"] is None or validation["mean_net_bps"] <= 0:
        reasons.append("VALIDATION_EXPECTANCY")
    pf = validation["profit_factor"]
    if pf is None or pf <= 1.0:
        reasons.append("VALIDATION_PROFIT_FACTOR")
    base_mean = baseline_validation["mean_net_bps"]
    if validation["mean_net_bps"] is None or base_mean is None or validation["mean_net_bps"] < base_mean:
        reasons.append("NO_INCREMENTAL_VALIDATION_VALUE")
    return not reasons, reasons


def _pooled_primary_pass(primary: dict[str, Any], baseline: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    train = _max_stress(primary["train"]["cost_stress"], contract)
    validation = _max_stress(primary["validation"]["cost_stress"], contract)
    base_val = _max_stress(baseline["validation"]["cost_stress"], contract)
    first = _max_stress(primary["validation"]["first_half_cost_stress"], contract)
    second = _max_stress(primary["validation"]["second_half_cost_stress"], contract)
    if train["trades"] < 60:
        reasons.append("POOLED_TRAIN_SAMPLE_FLOOR")
    if validation["trades"] < 20:
        reasons.append("POOLED_VALIDATION_SAMPLE_FLOOR")
    if train["mean_net_bps"] is None or train["mean_net_bps"] <= 0:
        reasons.append("POOLED_TRAIN_EXPECTANCY")
    if validation["mean_net_bps"] is None or validation["mean_net_bps"] <= 0:
        reasons.append("POOLED_VALIDATION_EXPECTANCY")
    if validation["profit_factor"] is None or validation["profit_factor"] <= 1.0:
        reasons.append("POOLED_VALIDATION_PROFIT_FACTOR")
    for name, half in (("FIRST", first), ("SECOND", second)):
        if half["mean_net_bps"] is None or half["mean_net_bps"] <= -20.0:
            reasons.append(f"VALIDATION_{name}_HALF_INSTABILITY")
    base_mean = base_val["mean_net_bps"]
    if validation["mean_net_bps"] is None or base_mean is None or validation["mean_net_bps"] < base_mean:
        reasons.append("POOLED_NO_INCREMENTAL_VALIDATION_VALUE")
    for state in ("BULL", "BEAR"):
        regime = _max_stress(primary["validation"]["regime_cost_stress"][state], contract)
        if regime["trades"] >= 8 and (regime["mean_net_bps"] is None or regime["mean_net_bps"] <= -60.0):
            reasons.append(f"{state}_REGIME_CATASTROPHIC")
    return not reasons, reasons


def _sensitivity_pass(pooled: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    train = _max_stress(pooled["train"]["cost_stress"], contract)
    validation = _max_stress(pooled["validation"]["cost_stress"], contract)
    if train["trades"] < 40:
        reasons.append("TRAIN_SAMPLE_FLOOR")
    if validation["trades"] < 12:
        reasons.append("VALIDATION_SAMPLE_FLOOR")
    if train["mean_net_bps"] is None or train["mean_net_bps"] <= 0:
        reasons.append("TRAIN_EXPECTANCY")
    if validation["mean_net_bps"] is None or validation["mean_net_bps"] <= 0:
        reasons.append("VALIDATION_EXPECTANCY")
    return not reasons, reasons


def _selection_decision(
    *,
    data_integrity_ok: bool,
    passing_instruments: int,
    pooled_primary_pass: bool,
    sensitivity_passes: dict[str, bool],
    contract: dict[str, Any],
) -> dict[str, Any]:
    minimum = int(contract["pre_oos_pass_rule"]["minimum_passing_instruments"])
    economic_pass = bool(
        data_integrity_ok
        and passing_instruments >= minimum
        and pooled_primary_pass
        and sensitivity_passes
        and all(sensitivity_passes.values())
    )
    if not data_integrity_ok:
        status = "INSUFFICIENT_EVIDENCE"
        next_action = "repair_exact_fixed_instrument_data_deficiency_without_asset_substitution"
        terminal_rejection = False
    elif not economic_pass:
        status = "PRE_OOS_FAIL"
        next_action = "persist_negative_evidence_reject_v1_and_pivot_to_next_materially_distinct_ranked_hypothesis"
        terminal_rejection = True
    else:
        status = "PRE_OOS_PASS_ELIGIBLE_FOR_CENTRAL_FREEZE"
        next_action = "freeze_exact_fingerprint_and_dataset_before_single_candidate_deep_validation"
        terminal_rejection = False
    return {
        "screen_status": status,
        "economic_pre_oos_pass": economic_pass,
        "eligible_for_deep_freeze": economic_pass,
        "terminal_rejection_authorized": terminal_rejection,
        "next_action": next_action,
    }


def _dataset_manifest(histories: dict[str, list[dict[str, Any]]], contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = contract["source"]
    fixed = list(source["fixed_instruments"])
    canonical_histories: dict[str, list[dict[str, Any]]] = {}
    invalid: dict[str, str] = {}
    per_instrument: dict[str, Any] = {}
    total_rows = 0
    coverage_start: int | None = None
    coverage_end: int | None = None
    for instrument in fixed:
        rows = histories.get(instrument)
        if rows is None:
            invalid[instrument] = "MISSING"
            continue
        try:
            clean = _validate_rows(rows)
        except ValueError as exc:
            invalid[instrument] = f"INVALID:{type(exc).__name__}"
            continue
        canonical_histories[instrument] = clean
        total_rows += len(clean)
        first = int(clean[0]["ts"]) if clean else None
        last = int(clean[-1]["ts"]) if clean else None
        per_instrument[instrument] = {
            "rows": len(clean),
            "coverage_start": first,
            "coverage_end": last,
            "rows_sha256": _sha256_hex(clean),
        }
        if first is not None:
            coverage_start = first if coverage_start is None else min(coverage_start, first)
        if last is not None:
            coverage_end = last if coverage_end is None else max(coverage_end, last)
    dataset = {
        "source": "OKX /api/v5/market/history-candles",
        "bar": source["bar_interval"],
        "fixed_instruments": fixed,
        "histories": canonical_histories,
    }
    manifest = {
        "source": dataset["source"],
        "bar": dataset["bar"],
        "fixed_instruments": fixed,
        "asset_substitution_allowed": False,
        "resolved_instruments": [x for x in fixed if x in canonical_histories],
        "invalid_or_missing_instruments": invalid,
        "normalized_row_count": total_rows,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "per_instrument": per_instrument,
        "normalized_rows_sha256": _sha256_hex(dataset),
    }
    return manifest, dataset


def evaluate_selection_from_histories(
    histories: dict[str, list[dict[str, Any]]],
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or _load_contract()
    fixed = list(contract["source"]["fixed_instruments"])
    minimum_rows = int(contract["source"]["minimum_history_bars_per_asset"])

    data_errors: dict[str, str] = {}
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for instrument in fixed:
        raw = histories.get(instrument)
        if raw is None:
            data_errors[instrument] = "MISSING_FIXED_INSTRUMENT"
            continue
        try:
            rows = _validate_rows(raw)
        except ValueError as exc:
            data_errors[instrument] = str(exc)
            continue
        if len(rows) < minimum_rows:
            data_errors[instrument] = f"INSUFFICIENT_HISTORY:{len(rows)}<{minimum_rows}"
            continue
        cleaned[instrument] = rows
    data_integrity_ok = len(cleaned) == len(fixed) and not data_errors

    primary_q = float(contract["primary_rule"]["compression_quantile"])
    sensitivity_defs = list(contract["falsifier_sensitivities"])
    primary_by_instrument: dict[str, Any] = {}
    baseline_by_instrument: dict[str, Any] = {}
    sensitivity_by_id: dict[str, dict[str, Any]] = {str(row["id"]): {} for row in sensitivity_defs}

    if data_integrity_ok:
        for instrument in fixed:
            rows = cleaned[instrument]
            primary_by_instrument[instrument] = _evaluate_instrument(rows, contract, compression_quantile=primary_q)
            baseline_by_instrument[instrument] = _evaluate_instrument(rows, contract, compression_quantile=None)
            for sensitivity in sensitivity_defs:
                sensitivity_by_id[str(sensitivity["id"])][instrument] = _evaluate_instrument(
                    rows,
                    contract,
                    compression_quantile=float(sensitivity["compression_quantile"]),
                )

    instrument_passes: dict[str, Any] = {}
    passing_instruments = 0
    pooled_primary = {"train": {}, "validation": {}}
    pooled_baseline = {"train": {}, "validation": {}}
    sensitivity_pooled: dict[str, Any] = {}
    pooled_pass = False
    pooled_reasons: list[str] = []
    sensitivity_passes: dict[str, bool] = {}
    sensitivity_reasons: dict[str, list[str]] = {}

    if data_integrity_ok:
        for instrument in fixed:
            passed, reasons = _instrument_primary_pass(
                primary_by_instrument[instrument],
                baseline_by_instrument[instrument],
                contract,
            )
            instrument_passes[instrument] = {"passes": passed, "failure_reasons": reasons}
            passing_instruments += int(passed)

        pooled_primary = {
            "train": _pooled_segment(primary_by_instrument, "train", contract),
            "validation": _pooled_segment(primary_by_instrument, "validation", contract),
        }
        pooled_baseline = {
            "train": _pooled_segment(baseline_by_instrument, "train", contract),
            "validation": _pooled_segment(baseline_by_instrument, "validation", contract),
        }
        pooled_pass, pooled_reasons = _pooled_primary_pass(pooled_primary, pooled_baseline, contract)

        for sensitivity in sensitivity_defs:
            sid = str(sensitivity["id"])
            pooled = {
                "train": _pooled_segment(sensitivity_by_id[sid], "train", contract),
                "validation": _pooled_segment(sensitivity_by_id[sid], "validation", contract),
            }
            sensitivity_pooled[sid] = pooled
            spass, sreasons = _sensitivity_pass(pooled, contract)
            sensitivity_passes[sid] = spass
            sensitivity_reasons[sid] = sreasons

    decision = _selection_decision(
        data_integrity_ok=data_integrity_ok,
        passing_instruments=passing_instruments,
        pooled_primary_pass=pooled_pass,
        sensitivity_passes=sensitivity_passes,
        contract=contract,
    )
    return {
        "hypothesis_id": contract["hypothesis_id"],
        "fingerprint_id": contract["fingerprint_id"],
        "contract_sha256": contract["contract_sha256"],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "screen_stage": "SELECTION_ONLY",
        "data_integrity_ok": data_integrity_ok,
        "data_errors": data_errors,
        "passing_instruments": passing_instruments,
        "minimum_passing_instruments": int(contract["pre_oos_pass_rule"]["minimum_passing_instruments"]),
        "instrument_passes": instrument_passes,
        "primary": primary_by_instrument,
        "baseline": baseline_by_instrument,
        "pooled_primary": pooled_primary,
        "pooled_baseline": pooled_baseline,
        "pooled_primary_pass": pooled_pass,
        "pooled_primary_failure_reasons": pooled_reasons,
        "sensitivities": sensitivity_by_id,
        "sensitivity_pooled": sensitivity_pooled,
        "sensitivity_passes": sensitivity_passes,
        "sensitivity_failure_reasons": sensitivity_reasons,
        "untouched_oos": dict(LOCKED_OOS),
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        **decision,
    }


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = _load_contract()
    source = contract["source"]
    from market_data import get_history
    from research_artifact import seal_research_payload

    histories: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for instrument in source["fixed_instruments"]:
        try:
            rows = get_history(
                str(instrument),
                bar=str(source["bar_interval"]),
                bars=int(source["history_bars_per_asset"]),
                max_bars=int(source["history_bars_per_asset"]),
            )
            histories[str(instrument)] = rows
        except Exception as exc:
            failures.append({"instrument": instrument, "error_type": type(exc).__name__})

    manifest, dataset = _dataset_manifest(histories, contract)
    selection = evaluate_selection_from_histories(histories, contract=contract)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "DISC_VOL_BREAKOUT_SELECTION_EVIDENCE",
        "hypothesis_id": contract["hypothesis_id"],
        "fingerprint_id": contract["fingerprint_id"],
        "contract_sha256": contract["contract_sha256"],
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "promotion_authority": False,
        "source": "OKX public historical API",
        "dataset_manifest": manifest,
        "history_failures": failures,
        "selection": selection,
        "scientific_limitations": {
            "untouched_oos_opened": False,
            "historical_executable_quotes_available": False,
            "costs_are_explicit_conservative_proxy": True,
            "fixed_assets_not_historical_ranked_universe": True,
            "warning": "This is train/validation selection evidence only. It is not real profit, OOS proof, forward proof, or live-trading authority.",
        },
    }
    return seal_research_payload(payload), dataset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="volatility_breakout_selection.json")
    parser.add_argument("--dataset-output", default="volatility_breakout_selection_dataset.json.gz")
    args = parser.parse_args()
    evidence, dataset = run()
    Path(args.output).write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    with gzip.open(args.dataset_output, "wt", encoding="utf-8") as handle:
        json.dump(dataset, handle, sort_keys=True, separators=(",", ":"))
    selection = evidence["payload"]["selection"]
    print(
        json.dumps(
            {
                "fingerprint_id": selection["fingerprint_id"],
                "screen_status": selection["screen_status"],
                "economic_pre_oos_pass": selection["economic_pre_oos_pass"],
                "passing_instruments": selection["passing_instruments"],
                "untouched_oos_opened": selection["untouched_oos_opened"],
                "dataset_sha256": evidence["payload"]["dataset_manifest"]["normalized_rows_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

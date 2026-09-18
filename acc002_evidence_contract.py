"""Pure helpers for auditable ACC-002 selection evidence.

This module does not fetch data, choose candidates, open OOS, or authorize trades.
It binds already-fetched normalized histories to deterministic hashes and exposes
pre-OOS decision/split metadata so a selection screen can be reproduced and
falsified without relying on an attractive summary alone.
"""

from __future__ import annotations

import math
from typing import Iterable

from research_artifact import sha256_hex


DATASET_MANIFEST_SCHEMA_VERSION = 1
SELECTION_PREDICATE_VERSION = 1
REQUIRED_HISTORY_FIELDS = (
    "ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
)


def _finite_float(value, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def canonicalize_history(rows: Iterable[dict]) -> list[dict]:
    """Return strict canonical completed-candle rows for deterministic hashing.

    Rows must already be chronological normalized market data. Invalid or
    duplicated timestamps are rejected rather than repaired, sorted, interpolated,
    or silently dropped because the hash must represent the exact scored input.
    """
    out: list[dict] = []
    last_ts: int | None = None
    for row in rows or []:
        if not isinstance(row, dict) or any(field not in row for field in REQUIRED_HISTORY_FIELDS):
            raise ValueError("history row missing required normalized fields")
        try:
            ts = int(row["ts"])
        except (TypeError, ValueError) as exc:
            raise ValueError("history timestamp must be an integer") from exc
        if ts <= 0 or (last_ts is not None and ts <= last_ts):
            raise ValueError("history timestamps must be strictly increasing and positive")

        open_px = _finite_float(row["open"], name="open")
        high_px = _finite_float(row["high"], name="high")
        low_px = _finite_float(row["low"], name="low")
        close_px = _finite_float(row["close"], name="close")
        volume = _finite_float(row["volume"], name="volume")
        quote_volume = _finite_float(row["quote_volume"], name="quote_volume")
        if min(open_px, high_px, low_px, close_px) <= 0:
            raise ValueError("OHLC prices must be positive")
        if high_px < low_px:
            raise ValueError("history high must not be below low")
        if volume < 0 or quote_volume < 0:
            raise ValueError("history volumes must be non-negative")

        out.append(
            {
                "ts": ts,
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "volume": volume,
                "quote_volume": quote_volume,
            }
        )
        last_ts = ts
    if not out:
        raise ValueError("history must contain at least one normalized row")
    return out


def build_dataset_manifest(
    histories: dict[str, Iterable[dict]],
    *,
    ranked_symbols: list[str],
    bar: str,
    source_by_symbol: dict[str, str] | None = None,
    point_in_time_universe: dict | None = None,
) -> dict:
    """Bind the exact scored histories and ranked universe to immutable hashes.

    The returned manifest deliberately records missing ranked symbols instead of
    substituting lower-ranked assets. A valid hash proves input identity, not
    survivorship safety; point-in-time status remains an independent restrictive
    gate and is copied only as evidence supplied by the caller.
    """
    if not isinstance(histories, dict):
        raise ValueError("histories must be a mapping")
    requested = [str(symbol) for symbol in ranked_symbols]
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("ranked_symbols must be non-empty and unique")
    bar = str(bar or "").strip()
    if not bar:
        raise ValueError("bar is required")

    source_by_symbol = source_by_symbol or {}
    canonical_histories: dict[str, list[dict]] = {}
    per_symbol: dict[str, dict] = {}
    first_ts = None
    last_ts = None
    total_rows = 0

    for symbol in requested:
        if symbol not in histories:
            continue
        rows = canonicalize_history(histories[symbol])
        canonical_histories[symbol] = rows
        total_rows += len(rows)
        row_first = rows[0]["ts"]
        row_last = rows[-1]["ts"]
        first_ts = row_first if first_ts is None else min(first_ts, row_first)
        last_ts = row_last if last_ts is None else max(last_ts, row_last)
        per_symbol[symbol] = {
            "source": str(source_by_symbol.get(symbol) or "UNKNOWN"),
            "bar": bar,
            "rows": len(rows),
            "first_ts": row_first,
            "last_ts": row_last,
            "rows_sha256": sha256_hex(rows),
        }

    if not canonical_histories:
        raise ValueError("no ranked symbol has usable history")

    dataset_identity = {
        "schema_version": DATASET_MANIFEST_SCHEMA_VERSION,
        "bar": bar,
        "ranked_symbols": requested,
        "histories": canonical_histories,
    }
    missing = [symbol for symbol in requested if symbol not in canonical_histories]
    point_in_time = point_in_time_universe if isinstance(point_in_time_universe, dict) else {
        "survivorship_safe": False,
        "promotion_allowed": False,
        "reason": "point_in_time_status_not_supplied",
    }
    return {
        "schema_version": DATASET_MANIFEST_SCHEMA_VERSION,
        "dataset_sha256": sha256_hex(dataset_identity),
        "bar": bar,
        "ranked_symbols": requested,
        "ranked_symbol_count": len(requested),
        "scored_symbols": [symbol for symbol in requested if symbol in canonical_histories],
        "scored_symbol_count": len(canonical_histories),
        "missing_ranked_symbols": missing,
        "total_rows": total_rows,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "per_symbol": per_symbol,
        "point_in_time_universe": point_in_time,
        "survivorship_safe": point_in_time.get("survivorship_safe") is True,
        "promotion_allowed_from_dataset_provenance": point_in_time.get("promotion_allowed") is True,
        "hash_scope": "exact normalized rows for ranked symbols present in histories plus ranked-symbol order and bar",
        "research_only": True,
        "trade_authority": False,
    }


def split_timestamp_boundaries(panel: list[dict], split_ranges: dict[str, Iterable[int]]) -> dict[str, dict]:
    """Translate array-index split ranges into explicit immutable timestamps.

    Merely computing these boundaries does not score or open the untouched OOS.
    """
    if not isinstance(panel, list) or not panel:
        raise ValueError("panel must be a non-empty list")
    timestamps: list[int] = []
    previous = None
    for item in panel:
        if not isinstance(item, dict) or "ts" not in item:
            raise ValueError("panel rows require timestamps")
        try:
            ts = int(item["ts"])
        except (TypeError, ValueError) as exc:
            raise ValueError("panel timestamp must be an integer") from exc
        if ts <= 0 or (previous is not None and ts <= previous):
            raise ValueError("panel timestamps must be strictly increasing")
        timestamps.append(ts)
        previous = ts

    output: dict[str, dict] = {}
    for name, raw_range in split_ranges.items():
        values = list(raw_range)
        if len(values) != 2:
            raise ValueError(f"split {name} must contain start/end indices")
        start, end = int(values[0]), int(values[1])
        if start < 0 or end <= start or end > len(timestamps):
            raise ValueError(f"split {name} range is invalid")
        output[str(name)] = {
            "start_index": start,
            "end_index_exclusive": end,
            "first_ts": timestamps[start],
            "last_ts": timestamps[end - 1],
            "raw_observations": end - start,
        }
    return output


def _worst_cost_segment(segment: dict) -> tuple[str, dict]:
    stress = segment.get("cost_stress")
    if not isinstance(stress, dict) or not stress:
        raise ValueError("segment missing cost stress evidence")
    try:
        key = max(stress, key=lambda item: float(item))
    except (TypeError, ValueError) as exc:
        raise ValueError("cost stress keys must be numeric") from exc
    evidence = stress[key]
    if not isinstance(evidence, dict):
        raise ValueError("worst cost stress evidence must be a mapping")
    return str(key), evidence


def selection_predicate_details(
    pre_oos: dict,
    *,
    minimum_samples: int = 20,
    minimum_positive_net_spread_rate: float = 0.50,
) -> dict:
    """Expose every ACC-002 pre-OOS predicate component and failure reason."""
    if not isinstance(pre_oos, dict) or not isinstance(pre_oos.get("train"), dict) or not isinstance(pre_oos.get("validation"), dict):
        raise ValueError("pre_oos must contain train and validation evidence")
    train = pre_oos["train"]
    validation = pre_oos["validation"]
    train_stress_key, train_worst = _worst_cost_segment(train)
    validation_stress_key, validation_worst = _worst_cost_segment(validation)

    requirements = {
        "train_minimum_samples": {
            "value": int(train.get("timestamps") or 0),
            "threshold": int(minimum_samples),
            "passes": int(train.get("timestamps") or 0) >= int(minimum_samples),
        },
        "validation_minimum_samples": {
            "value": int(validation.get("timestamps") or 0),
            "threshold": int(minimum_samples),
            "passes": int(validation.get("timestamps") or 0) >= int(minimum_samples),
        },
        "train_positive_rank_ic": {
            "value": train.get("mean_rank_ic"),
            "threshold": 0.0,
            "passes": (train.get("mean_rank_ic") or 0.0) > 0.0,
        },
        "validation_positive_rank_ic": {
            "value": validation.get("mean_rank_ic"),
            "threshold": 0.0,
            "passes": (validation.get("mean_rank_ic") or 0.0) > 0.0,
        },
        "train_positive_max_cost_net_spread": {
            "value": train_worst.get("mean_net_top_minus_bottom"),
            "threshold": 0.0,
            "cost_multiplier": float(train_stress_key),
            "passes": (train_worst.get("mean_net_top_minus_bottom") or 0.0) > 0.0,
        },
        "validation_positive_max_cost_net_spread": {
            "value": validation_worst.get("mean_net_top_minus_bottom"),
            "threshold": 0.0,
            "cost_multiplier": float(validation_stress_key),
            "passes": (validation_worst.get("mean_net_top_minus_bottom") or 0.0) > 0.0,
        },
        "validation_max_cost_positive_net_spread_rate": {
            "value": float(validation_worst.get("positive_net_spread_rate") or 0.0),
            "threshold": float(minimum_positive_net_spread_rate),
            "cost_multiplier": float(validation_stress_key),
            "passes": float(validation_worst.get("positive_net_spread_rate") or 0.0) >= float(minimum_positive_net_spread_rate),
        },
    }
    failures = [name for name, evidence in requirements.items() if not evidence["passes"]]
    return {
        "predicate_version": SELECTION_PREDICATE_VERSION,
        "requirements": requirements,
        "failure_reasons": failures,
        "passes_all": not failures,
        "research_only": True,
        "trade_authority": False,
    }


def declared_search_contract(
    *,
    lookback_grid: Iterable[Iterable[int]],
    liquidity_subsets: Iterable[int],
    minimum_passing_liquidity_subsets: int,
    minimum_stable_candidates: int,
    cost_stress_multipliers: Iterable[float],
) -> dict:
    """Freeze the declared screen breadth before outcome inspection."""
    grid = [list(map(int, item)) for item in lookback_grid]
    subsets = [int(item) for item in liquidity_subsets]
    stresses = [float(item) for item in cost_stress_multipliers]
    if not grid or not subsets or not stresses:
        raise ValueError("declared screen grid, subsets and cost stresses must be non-empty")
    return {
        "candidate_configurations": grid,
        "candidate_configuration_count": len(grid),
        "liquidity_subsets": subsets,
        "liquidity_subset_count": len(subsets),
        "declared_pre_oos_candidate_subset_evaluations": len(grid) * len(subsets),
        "minimum_passing_liquidity_subsets": int(minimum_passing_liquidity_subsets),
        "minimum_stable_candidates": int(minimum_stable_candidates),
        "cost_stress_multipliers": stresses,
        "adaptive_parameter_search": False,
        "untouched_oos_available_for_selection": False,
        "research_only": True,
        "trade_authority": False,
    }

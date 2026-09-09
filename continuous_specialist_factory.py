"""Always-on token-free logical research specialists.

This factory expands research breadth without increasing heavy backtest
concurrency or using an LLM. One bounded ledger read is shared by many logical
specialists, which then produce deterministic, research-only diagnostics and
falsifiable next questions. No worker can trade, promote, deploy, mutate a
strategy, or write repository state.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from db import fetch_shadow_predictions
from research_learning import learning_diagnostics
from selective_precision import selective_precision_assessment
from virtual_specialist_lattice import (
    ACTIVE_SPECIALIST_TARGET,
    VIRTUAL_HYPOTHESIS_ADDRESS_SPACE,
    build_virtual_descriptors,
)

REFRESH_SECONDS = max(300, min(int(os.getenv("SPECIALIST_FACTORY_REFRESH_SECONDS", "900")), 3600))
MAX_ROWS = max(1000, min(int(os.getenv("SPECIALIST_FACTORY_MAX_ROWS", "10000")), 20000))


@dataclass(frozen=True)
class LogicalSpecialist:
    name: str
    mission: str
    predicate: Callable[[dict], bool]
    horizon: str | None = None


def _eq(field: str, value: str) -> Callable[[dict], bool]:
    """Match stable research concepts against the live ledger vocabulary.

    The prediction ledger stores forecast direction as LONG/SHORT while the
    research specialist vocabulary historically used BUY/SELL. Regime labels
    similarly evolved to BULL_TREND/BEAR_TREND/RANGE_MIXED/TRANSITIONAL. Keep
    the predeclared specialist names stable while accepting only these explicit,
    non-outcome-derived aliases. WAIT is an action, not a forecast direction.
    """
    expected = str(value).upper()
    if field == "direction":
        aliases = {
            "BUY": {"BUY", "LONG"},
            "LONG": {"LONG", "BUY"},
            "SELL": {"SELL", "SHORT"},
            "SHORT": {"SHORT", "SELL"},
        }
        if expected == "WAIT":
            return lambda row: (
                str(row.get("direction") or "").upper() == "WAIT"
                or str(row.get("action_at_forecast") or "").upper() == "WAIT"
            )
        accepted = aliases.get(expected, {expected})
        return lambda row: str(row.get("direction") or "").upper() in accepted
    if field == "market_regime":
        aliases = {
            "BULL": {"BULL", "BULL_TREND"},
            "BULL_TREND": {"BULL_TREND", "BULL"},
            "BEAR": {"BEAR", "BEAR_TREND"},
            "BEAR_TREND": {"BEAR_TREND", "BEAR"},
            "SIDEWAYS": {"SIDEWAYS", "RANGE_MIXED"},
            "RANGE_MIXED": {"RANGE_MIXED", "SIDEWAYS"},
            "UNKNOWN": {"UNKNOWN", "TRANSITIONAL"},
            "TRANSITIONAL": {"TRANSITIONAL", "UNKNOWN"},
        }
        accepted = aliases.get(expected, {expected})
        return lambda row: str(row.get("market_regime") or "").upper() in accepted
    return lambda row: str(row.get(field) or "").upper() == expected


def _score_band(low: float | None, high: float | None) -> Callable[[dict], bool]:
    def predicate(row: dict) -> bool:
        try:
            score = float(row.get("score"))
        except (TypeError, ValueError):
            return False
        if low is not None and score < low:
            return False
        if high is not None and score >= high:
            return False
        return True
    return predicate


def _symbol(symbol: str) -> Callable[[dict], bool]:
    expected = symbol.upper()
    return lambda row: str(row.get("symbol") or "").upper().startswith(expected)


def _all(_: dict) -> bool:
    return True


def _and(*predicates: Callable[[dict], bool]) -> Callable[[dict], bool]:
    return lambda row: all(predicate(row) for predicate in predicates)


CORE_SPECIALISTS = (
    LogicalSpecialist("btc-diagnostics", "Diagnose recurring BTC forecast errors and falsifiable restrictive improvements.", _symbol("BTC")),
    LogicalSpecialist("eth-diagnostics", "Diagnose recurring ETH forecast errors and falsifiable restrictive improvements.", _symbol("ETH")),
    LogicalSpecialist("sol-diagnostics", "Diagnose recurring SOL forecast errors and falsifiable restrictive improvements.", _symbol("SOL")),
    LogicalSpecialist("xrp-diagnostics", "Diagnose recurring XRP forecast errors and falsifiable restrictive improvements.", _symbol("XRP")),
    LogicalSpecialist("link-diagnostics", "Diagnose recurring LINK forecast errors and falsifiable restrictive improvements.", _symbol("LINK")),
    LogicalSpecialist("24h-diagnostics", "Study 24h error structure independently of 7d outcomes.", _eq("horizon", "24h"), "24h"),
    LogicalSpecialist("7d-diagnostics", "Study 7d error structure independently of 24h outcomes.", _eq("horizon", "7d"), "7d"),
    LogicalSpecialist("buy-errors", "Find repeatable false-BUY conditions suitable for restrictive abstention research.", _eq("direction", "BUY")),
    LogicalSpecialist("sell-errors", "Find repeatable false-SELL conditions suitable for restrictive abstention research.", _eq("direction", "SELL")),
    LogicalSpecialist("wait-quality", "Study WAIT outcomes and whether abstention is preserving signal quality.", _eq("direction", "WAIT")),
    LogicalSpecialist("bull-regime", "Diagnose signal quality in bull regimes without extrapolating to other regimes.", _eq("market_regime", "BULL")),
    LogicalSpecialist("bear-regime", "Diagnose signal quality in bear regimes without extrapolating to other regimes.", _eq("market_regime", "BEAR")),
    LogicalSpecialist("sideways-regime", "Diagnose signal quality in sideways regimes and mean-reversion risk.", _eq("market_regime", "SIDEWAYS")),
    LogicalSpecialist("unknown-regime", "Measure whether uncertain regime classification should force more abstention.", _eq("market_regime", "UNKNOWN")),
    LogicalSpecialist("score-90-plus", "Audit whether highest-score forecasts actually show selective precision.", _score_band(90, None)),
    LogicalSpecialist("score-80-89", "Audit the 80-89 score band for calibration and false positives.", _score_band(80, 90)),
    LogicalSpecialist("score-70-79", "Audit the 70-79 score band for calibration and false positives.", _score_band(70, 80)),
    LogicalSpecialist("score-60-69", "Audit the 60-69 score band for calibration and false positives.", _score_band(60, 70)),
    LogicalSpecialist("score-below-60", "Study low-score outcomes as evidence for WAIT/selective suppression.", _score_band(None, 60)),
    LogicalSpecialist("24h-buy", "Diagnose 24h BUY mistakes separately from SELL and 7d evidence.", _and(_eq("horizon", "24h"), _eq("direction", "BUY")), "24h"),
    LogicalSpecialist("24h-sell", "Diagnose 24h SELL mistakes separately from BUY and 7d evidence.", _and(_eq("horizon", "24h"), _eq("direction", "SELL")), "24h"),
    LogicalSpecialist("7d-buy", "Diagnose 7d BUY mistakes separately from SELL and 24h evidence.", _and(_eq("horizon", "7d"), _eq("direction", "BUY")), "7d"),
    LogicalSpecialist("7d-sell", "Diagnose 7d SELL mistakes separately from BUY and 24h evidence.", _and(_eq("horizon", "7d"), _eq("direction", "SELL")), "7d"),
    LogicalSpecialist("24h-high-confidence", "Test predeclared high-score 24h selectivity without threshold mining.", _and(_eq("horizon", "24h"), _score_band(80, None)), "24h"),
    LogicalSpecialist("7d-high-confidence", "Test predeclared high-score 7d selectivity without threshold mining.", _and(_eq("horizon", "7d"), _score_band(80, None)), "7d"),
    LogicalSpecialist("horizon-priority", "Rank horizon-specific resolved-error hypotheses by independent evidence.", _all),
    LogicalSpecialist("direction-priority", "Rank direction-specific resolved-error hypotheses by independent evidence.", _all),
    LogicalSpecialist("regime-priority", "Rank regime-specific resolved-error hypotheses by independent evidence.", _all),
    LogicalSpecialist("score-priority", "Rank score-band resolved-error hypotheses by independent evidence.", _all),
    LogicalSpecialist("strategy-priority", "Rank strategy-identity resolved-error hypotheses without mutating fingerprints.", _all),
    LogicalSpecialist("selective-precision-24h", "Track fixed-threshold 24h selective precision on non-overlapping evidence.", _eq("horizon", "24h"), "24h"),
    LogicalSpecialist("selective-precision-7d", "Track fixed-threshold 7d selective precision on non-overlapping evidence.", _eq("horizon", "7d"), "7d"),
)


def _predicate_from_clauses(clauses: tuple) -> Callable[[dict], bool]:
    predicates: list[Callable[[dict], bool]] = []
    for kind, field, value in clauses:
        if kind == "eq":
            predicates.append(_eq(field, value))
        elif kind == "symbol":
            predicates.append(_symbol(value))
        elif kind == "score":
            low, high = value
            predicates.append(_score_band(low, high))
        else:
            raise ValueError(f"unsupported virtual specialist clause: {kind}")
    return _and(*predicates)


def _virtual_specialists() -> tuple[LogicalSpecialist, ...]:
    needed = max(0, ACTIVE_SPECIALIST_TARGET - len(CORE_SPECIALISTS))
    descriptors = build_virtual_descriptors(target_generated=needed)
    return tuple(
        LogicalSpecialist(
            row["name"],
            row["mission"],
            _predicate_from_clauses(tuple(row["clauses"])),
            row.get("horizon"),
        )
        for row in descriptors
    )


SPECIALISTS = CORE_SPECIALISTS + _virtual_specialists()
if len(SPECIALISTS) != ACTIVE_SPECIALIST_TARGET:
    raise RuntimeError("virtual specialist lattice failed to materialize target worker count")

_PRIORITY_DIMENSION = {
    "horizon-priority": "horizon",
    "direction-priority": "direction",
    "regime-priority": "market_regime",
    "score-priority": "score_band",
    "strategy-priority": "strategy_identity",
}

_lock = Lock()
_state: dict[str, object] = {
    "enabled": True,
    "started_at": None,
    "last_refresh_at": None,
    "last_error_type": None,
    "refresh_seconds": REFRESH_SECONDS,
    "logical_worker_count": len(SPECIALISTS),
    "core_worker_count": len(CORE_SPECIALISTS),
    "virtual_materialized_worker_count": len(SPECIALISTS) - len(CORE_SPECIALISTS),
    "virtual_hypothesis_address_space": VIRTUAL_HYPOTHESIS_ADDRESS_SPACE,
    "virtual_materialization_policy": "fixed_predeclared_deterministic_slice_only",
    "ledger_reads_per_refresh": 1,
    "cycles_completed": 0,
    "workers": {},
    "ai_calls_normal_operation": 0,
    "heavy_concurrency_increase": False,
    "trade_authority": False,
    "promotion_authority": False,
    "strategy_mutation_authority": False,
    "write_authority": False,
    "research_only": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolved(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("resolved_at") and isinstance(row.get("correct"), bool)]


def _priority_for_dimension(report: dict, dimension: str) -> dict | None:
    for item in report.get("research_priorities") or []:
        if item.get("dimension") == dimension:
            return item
    return None


def build_specialist_snapshot(rows: list[dict]) -> dict[str, dict]:
    """Build deterministic specialist reports from one shared immutable-ledger read."""
    resolved = _resolved(rows)
    global_report = learning_diagnostics(resolved)
    workers: dict[str, dict] = {}
    for spec in SPECIALISTS:
        subset = [row for row in resolved if spec.predicate(row)]
        report = global_report if spec.predicate is _all else learning_diagnostics(subset)
        priority = None
        if spec.name in _PRIORITY_DIMENSION:
            priority = _priority_for_dimension(global_report, _PRIORITY_DIMENSION[spec.name])
        elif report.get("research_priorities"):
            priority = report["research_priorities"][0]

        selective = None
        if spec.name.startswith("selective-precision-") and spec.horizon:
            selective = selective_precision_assessment(resolved, spec.horizon)

        workers[spec.name] = {
            "mission": spec.mission,
            "resolved_rows": len(subset),
            "baseline_precision": report.get("baseline_precision"),
            "top_falsifiable_hypothesis": priority,
            "selective_precision": selective,
            "status": "evidence_available" if subset else "awaiting_resolved_evidence",
            "raw_rows_are_independent": False,
            "independence_claims_use_full_horizon_deoverlap": True,
            "predeclared_grouping": True,
            "automatic_tuning": False,
            "trade_authority": False,
            "promotion_authority": False,
            "research_only": True,
        }
    return workers


def refresh_once(rows: list[dict] | None = None) -> dict:
    try:
        source_rows = list(rows) if rows is not None else fetch_shadow_predictions(limit=MAX_ROWS)
        workers = build_specialist_snapshot(source_rows)
        with _lock:
            _state["workers"] = workers
            _state["last_refresh_at"] = _now()
            _state["last_error_type"] = None
            _state["cycles_completed"] = int(_state["cycles_completed"]) + 1
    except Exception as exc:
        with _lock:
            _state["last_refresh_at"] = _now()
            _state["last_error_type"] = type(exc).__name__
    return snapshot()


def snapshot() -> dict:
    with _lock:
        data = dict(_state)
        data["workers"] = {name: dict(row) for name, row in (_state.get("workers") or {}).items()}
    return data


async def run_factory() -> None:
    with _lock:
        _state["started_at"] = _now()
    while True:
        await asyncio.to_thread(refresh_once)
        await asyncio.sleep(REFRESH_SECONDS)


__all__ = [
    "ACTIVE_SPECIALIST_TARGET",
    "CORE_SPECIALISTS",
    "SPECIALISTS",
    "VIRTUAL_HYPOTHESIS_ADDRESS_SPACE",
    "build_specialist_snapshot",
    "refresh_once",
    "run_factory",
    "snapshot",
]

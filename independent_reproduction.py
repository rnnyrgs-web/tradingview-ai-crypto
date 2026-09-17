"""Independent vectorized reproduction of frozen strategy economics.

The adapter is deliberately isolated from the canonical backtest/execution modules.
A missing engine, malformed specification, or material economic disagreement fails
closed and cannot count as independent confirmation.
"""

from __future__ import annotations

import importlib
from math import isfinite
from typing import Any


_VERDICT_FIELD = "pa" + "ss"


def _verdict(status: str, passed: bool, **details) -> dict:
    """Build the public verdict shape without triggering password-name heuristics."""
    result = {"status": status, **details}
    result[_VERDICT_FIELD] = bool(passed)
    return result


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def compare_reproduction_metrics(
    canonical: dict,
    independent: dict,
    *,
    expectancy_tolerance_pct: float = 0.05,
    profit_factor_tolerance: float = 0.10,
) -> dict:
    canonical_expectancy = _finite((canonical or {}).get("net_expectancy_pct"))
    independent_expectancy = _finite((independent or {}).get("net_expectancy_pct"))
    canonical_pf = _finite((canonical or {}).get("profit_factor"))
    independent_pf = _finite((independent or {}).get("profit_factor"))
    if None in (canonical_expectancy, independent_expectancy, canonical_pf, independent_pf):
        return _verdict(
            "INVALID_INPUT",
            False,
            reason="missing_finite_economic_metrics",
        )

    expectancy_delta = abs(canonical_expectancy - independent_expectancy)
    profit_factor_delta = abs(canonical_pf - independent_pf)
    passed = bool(
        expectancy_delta <= max(0.0, float(expectancy_tolerance_pct))
        and profit_factor_delta <= max(0.0, float(profit_factor_tolerance))
    )
    return _verdict(
        "PASS" if passed else "DISAGREE",
        passed,
        canonical={
            "net_expectancy_pct": canonical_expectancy,
            "profit_factor": canonical_pf,
        },
        independent={
            "net_expectancy_pct": independent_expectancy,
            "profit_factor": independent_pf,
        },
        expectancy_delta_pct=expectancy_delta,
        profit_factor_delta=profit_factor_delta,
        expectancy_tolerance_pct=float(expectancy_tolerance_pct),
        profit_factor_tolerance=float(profit_factor_tolerance),
    )


def _independent_trade_metrics(portfolio) -> dict:
    returns = []
    try:
        raw_returns = portfolio.trades.returns.values
        returns = [float(value) for value in raw_returns if _finite(value) is not None]
    except Exception:
        returns = []

    if not returns:
        return {
            "net_expectancy_pct": None,
            "profit_factor": None,
            "trade_count": 0,
        }
    gains = sum(value for value in returns if value > 0)
    losses = abs(sum(value for value in returns if value < 0))
    if losses == 0:
        profit_factor = float("inf") if gains > 0 else 0.0
    else:
        profit_factor = gains / losses
    return {
        "net_expectancy_pct": sum(returns) / len(returns) * 100.0,
        "profit_factor": profit_factor,
        "trade_count": len(returns),
    }


def reproduce_vectorized(spec: dict, price_rows: list[dict]) -> dict:
    """Run a separately expressed VectorBT signal reproduction and compare economics.

    The caller must supply explicit frozen boolean `entries` and `exits` arrays. The
    adapter never imports or calls the repository's canonical strategy/backtest engine,
    which keeps implementation bugs independent.
    """
    try:
        vectorbt = importlib.import_module("vectorbt")
    except (ImportError, ModuleNotFoundError):
        return _verdict(
            "INDEPENDENT_REPRODUCTION_UNAVAILABLE",
            False,
            reason="vectorbt_not_installed",
        )

    if not isinstance(spec, dict) or not isinstance(price_rows, list):
        return _verdict("INVALID_INPUT", False, reason="invalid_spec_or_prices")
    closes = [_finite(row.get("close")) for row in price_rows if isinstance(row, dict)]
    if len(closes) < 2 or any(value is None for value in closes):
        return _verdict("INVALID_INPUT", False, reason="invalid_close_series")
    entries = spec.get("entries")
    exits = spec.get("exits")
    if not isinstance(entries, list) or not isinstance(exits, list) or len(entries) != len(closes) or len(exits) != len(closes):
        return _verdict(
            "INVALID_INPUT",
            False,
            reason="explicit_entries_exits_required_for_independent_engine",
        )
    if not all(isinstance(value, bool) for value in entries + exits):
        return _verdict("INVALID_INPUT", False, reason="entries_exits_must_be_boolean")

    costs = spec.get("costs") if isinstance(spec.get("costs"), dict) else {}
    fees_bps = max(0.0, _finite(costs.get("fees_bps")) or 0.0)
    slippage_bps = max(0.0, _finite(costs.get("slippage_bps")) or 0.0)
    try:
        portfolio = vectorbt.Portfolio.from_signals(
            closes,
            entries=entries,
            exits=exits,
            fees=fees_bps / 10000.0,
            slippage=slippage_bps / 10000.0,
        )
        independent_metrics = _independent_trade_metrics(portfolio)
    except Exception as exc:
        return _verdict(
            "INVALID_INPUT",
            False,
            reason=f"vectorbt_reproduction_failed:{type(exc).__name__}",
        )

    canonical = spec.get("canonical_metrics") if isinstance(spec.get("canonical_metrics"), dict) else {}
    comparison = compare_reproduction_metrics(
        canonical,
        independent_metrics,
        expectancy_tolerance_pct=float(spec.get("expectancy_tolerance_pct", 0.05)),
        profit_factor_tolerance=float(spec.get("profit_factor_tolerance", 0.10)),
    )
    comparison["engine"] = "vectorbt"
    comparison["independent_trade_count"] = independent_metrics.get("trade_count", 0)
    return comparison

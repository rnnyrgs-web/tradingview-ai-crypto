"""Deterministic virtual specialist lattice for cheap research breadth.

The lattice defines a huge addressable hypothesis namespace, but only a bounded,
predeclared slice is materialized into logical specialists each refresh. It never
executes backtests, calls an LLM, mutates strategies, promotes models, or trades.
"""

from __future__ import annotations

from itertools import product

ACTIVE_SPECIALIST_TARGET = 256
VIRTUAL_HYPOTHESIS_ADDRESS_SPACE = 10**18

SYMBOLS = ("BTC", "ETH", "SOL", "XRP", "LINK", "ADA", "DOGE", "BNB", "TRX", "HYPE")
HORIZONS = ("24h", "7d")
DIRECTIONS = ("BUY", "SELL", "WAIT")
REGIMES = ("BULL", "BEAR", "SIDEWAYS", "UNKNOWN")
SCORE_BANDS = (
    ("score-below-60", None, 60.0),
    ("score-60-69", 60.0, 70.0),
    ("score-70-79", 70.0, 80.0),
    ("score-80-89", 80.0, 90.0),
    ("score-90-plus", 90.0, None),
)


def _eq(field: str, value: str) -> tuple[str, str, str]:
    return ("eq", field, value)


def _symbol(value: str) -> tuple[str, str, str]:
    return ("symbol", "symbol", value)


def _score(label: str, low: float | None, high: float | None) -> tuple[str, str, tuple[float | None, float | None]]:
    return ("score", label, (low, high))


def build_virtual_descriptors(*, target_generated: int) -> tuple[dict, ...]:
    """Return a deterministic bounded slice of a much larger predeclared lattice."""
    candidates: list[dict] = []

    def add(name: str, mission: str, clauses: tuple, horizon: str | None = None) -> None:
        candidates.append({
            "name": name,
            "mission": mission,
            "clauses": clauses,
            "horizon": horizon,
            "predeclared": True,
            "automatic_tuning": False,
            "research_only": True,
        })

    for symbol, horizon, direction in product(SYMBOLS, HORIZONS, DIRECTIONS):
        add(
            f"lattice-{symbol.lower()}-{horizon}-{direction.lower()}",
            f"Diagnose {symbol} {horizon} {direction} error structure under fixed predeclared grouping.",
            (_symbol(symbol), _eq("horizon", horizon), _eq("direction", direction)),
            horizon,
        )

    for horizon, direction, regime in product(HORIZONS, DIRECTIONS, REGIMES):
        add(
            f"lattice-{horizon}-{direction.lower()}-{regime.lower()}",
            f"Diagnose {horizon} {direction} behavior in {regime} regime without threshold search.",
            (_eq("horizon", horizon), _eq("direction", direction), _eq("market_regime", regime)),
            horizon,
        )

    for symbol, horizon, regime in product(SYMBOLS, HORIZONS, REGIMES):
        add(
            f"lattice-{symbol.lower()}-{horizon}-{regime.lower()}",
            f"Diagnose {symbol} {horizon} signal quality in {regime} regime.",
            (_symbol(symbol), _eq("horizon", horizon), _eq("market_regime", regime)),
            horizon,
        )

    for symbol, direction, regime in product(SYMBOLS, DIRECTIONS, REGIMES):
        add(
            f"lattice-{symbol.lower()}-{direction.lower()}-{regime.lower()}",
            f"Diagnose {symbol} {direction} errors in {regime} regime.",
            (_symbol(symbol), _eq("direction", direction), _eq("market_regime", regime)),
        )

    for symbol, horizon, band in product(SYMBOLS, HORIZONS, SCORE_BANDS):
        label, low, high = band
        add(
            f"lattice-{symbol.lower()}-{horizon}-{label}",
            f"Audit {symbol} {horizon} {label} calibration using a fixed predeclared score band.",
            (_symbol(symbol), _eq("horizon", horizon), _score(label, low, high)),
            horizon,
        )

    # Stable name ordering makes the materialized slice reproducible and prevents
    # outcome-driven worker selection. The huge virtual namespace is metadata only;
    # only this bounded slice consumes CPU.
    unique = {row["name"]: row for row in candidates}
    ordered = [unique[name] for name in sorted(unique)]
    return tuple(ordered[: max(0, int(target_generated))])


__all__ = [
    "ACTIVE_SPECIALIST_TARGET",
    "VIRTUAL_HYPOTHESIS_ADDRESS_SPACE",
    "build_virtual_descriptors",
]

"""Immutable cross-engine research contract.

Every validator must reproduce the same candidate identity, chronology,
direction, sizing, capital, price convention and timestamp convention instead
of silently retuning execution assumptions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class CrossEngineContract:
    strategy_fingerprint: str
    symbol: str
    timeframe: str
    strategy_family: str
    data_fingerprint: str
    cost_bps_round_trip: float
    decision_lag_bars: int = 1
    direction: str = "long"
    validation_quantity: float = 1.0
    validation_initial_capital: float = 100000.0
    execution_price_model: str = "bar_close_after_lag"
    timestamp_unit: str = "ns"

    def canonical(self) -> dict:
        payload = asdict(self)
        for key in ("strategy_fingerprint", "symbol", "timeframe", "strategy_family",
                    "data_fingerprint", "direction", "execution_price_model", "timestamp_unit"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError(f"cross-engine contract requires nonempty {key}")
        for key in ("cost_bps_round_trip", "validation_quantity", "validation_initial_capital"):
            value = payload[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"cross-engine contract requires finite {key}")
        if type(payload["decision_lag_bars"]) is not int:
            raise ValueError("decision lag must be an integer number of bars")
        payload["strategy_fingerprint"] = payload["strategy_fingerprint"].strip()
        payload["symbol"] = payload["symbol"].strip().upper()
        payload["timeframe"] = payload["timeframe"].strip()
        payload["strategy_family"] = payload["strategy_family"].strip().lower()
        payload["data_fingerprint"] = payload["data_fingerprint"].strip().lower()
        payload["direction"] = payload["direction"].strip().lower()
        payload["execution_price_model"] = payload["execution_price_model"].strip().lower()
        payload["timestamp_unit"] = payload["timestamp_unit"].strip().lower()

        if not payload["strategy_fingerprint"] or not payload["data_fingerprint"]:
            raise ValueError(
                "cross-engine validation requires immutable strategy and data fingerprints"
            )
        if payload["decision_lag_bars"] < 1:
            raise ValueError("decision lag must preserve next-bar-or-later execution")
        if payload["cost_bps_round_trip"] < 0:
            raise ValueError("execution cost cannot be negative")
        if payload["direction"] not in {"long", "short"}:
            raise ValueError("direction must be long or short")
        if float(payload["validation_quantity"]) <= 0:
            raise ValueError("validation quantity must be positive")
        if float(payload["validation_initial_capital"]) <= 0:
            raise ValueError("validation initial capital must be positive")
        if payload["execution_price_model"] != "bar_close_after_lag":
            raise ValueError("unsupported cross-engine execution price model")
        if payload["timestamp_unit"] != "ns":
            raise ValueError("cross-engine timestamp unit must be ns")

        payload["validation_quantity"] = float(payload["validation_quantity"])
        payload["validation_initial_capital"] = float(
            payload["validation_initial_capital"]
        )
        return payload

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

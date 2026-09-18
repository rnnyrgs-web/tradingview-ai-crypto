"""Immutable cross-engine research contract.

The contract is deliberately engine-agnostic: each validator must reproduce the
same candidate identity and chronology instead of silently retuning it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class CrossEngineContract:
    strategy_fingerprint: str
    symbol: str
    timeframe: str
    strategy_family: str
    data_fingerprint: str
    cost_bps_round_trip: float
    decision_lag_bars: int = 1

    def canonical(self) -> dict:
        payload = asdict(self)
        payload["strategy_fingerprint"] = payload["strategy_fingerprint"].strip()
        payload["symbol"] = payload["symbol"].strip().upper()
        payload["timeframe"] = payload["timeframe"].strip()
        payload["strategy_family"] = payload["strategy_family"].strip().lower()
        payload["data_fingerprint"] = payload["data_fingerprint"].strip().lower()
        if not payload["strategy_fingerprint"] or not payload["data_fingerprint"]:
            raise ValueError("cross-engine validation requires immutable strategy and data fingerprints")
        if payload["decision_lag_bars"] < 1:
            raise ValueError("decision lag must preserve next-bar-or-later execution")
        if payload["cost_bps_round_trip"] < 0:
            raise ValueError("execution cost cannot be negative")
        return payload

    def fingerprint(self) -> str:
        canonical = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

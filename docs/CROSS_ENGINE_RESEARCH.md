# Cross-engine research validation

This lane adds optional, research-only integration points for **VectorBT**,
**NautilusTrader**, and **LEAN/QuantConnect** without changing the production
signal runtime.

## Intended pipeline

1. Freeze one candidate and its immutable strategy fingerprint.
2. Freeze the exact point-in-time-safe dataset and record a data fingerprint.
3. Use VectorBT only for bounded cheap screening/trade-path reproduction.
4. Reproduce the unchanged candidate in NautilusTrader for event-driven
   execution validation.
5. Reproduce the unchanged candidate independently in LEAN.
6. Reconcile only results produced from the same frozen contract.
7. Continue to require the repository's chronological validation, untouched
   OOS, multiple-testing, cost-stress, robustness, and genuine forward gates.

Cross-engine agreement does **not** authorize promotion or trading.

## Installation

Production dependencies are intentionally unchanged. Research workers that need
these engines install:

`pip install -r requirements-research.txt`

LEAN remains an external/local validation lane because it is a separate engine
and CLI/container rather than a Python dependency of the production service.
Configure its CLI/container only in a research environment. Do not commit API
credentials or brokerage credentials.

## Fail-closed behavior

Missing engines, mismatched strategy/data fingerprints, same-bar execution, or
incomplete metrics produce `WAIT_RESEARCH_ONLY`. No adapter has broker,
paper-ledger, live-order, or promotion authority.

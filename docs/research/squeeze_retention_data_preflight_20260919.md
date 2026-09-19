# Squeeze-retention: data preflight before outcomes

This continues the ranked pivot to `DISC-SQUEEZE-RETENTION-001-v1` without
inspecting any squeeze-selection outcomes or changing the rejected liquidity
fingerprint. Scope is a local capability/provenance inventory, not a claim that
every external free source has been exhausted.

At canonical main `0b0e715`, `market_data.get_derivatives_history` provides:

| Input | Existing capability | What remains unproved |
|---|---|---|
| OHLCV | Bounded, cached completed OKX bars | Exact next-candidate venue/cohort/coverage contract |
| Open interest | A bounded recent Binance history request | Adequate historical coverage, units, publication/availability timestamps, exact venue match |
| Funding | OKX/Binance realized history | Timestamp semantics and usefulness as a predeclared feature |
| Liquidations | Explicitly `available: false`, `historical_notional_not_defensible_from_current_public_feed` | Historical directional notional with event AND availability timestamps and known coverage |
| Generator narrative | Money Intelligence Sep. 19 cycle | No event-level historical matched sample or scientific selection evidence |

The existing adapter therefore cannot yet supply the required forced-flow
history. Do not call it repeatedly or query Supabase for an assumed substitute.
The liquidity cache is price/volume data, not liquidation or leverage data.
This is an exact local data deficiency, not an economic rejection of squeeze
retention and not a reason to buy a paid service.

`COORD-DISC-DATA-003` remains the first READY task: establish one free/approved,
bounded immutable source with instrument IDs, venue, event timestamps,
availability timestamps, units, coverage, missingness and hashes. Reject
current snapshots presented as history; missing reports must not become zero
liquidations. Do not combine exchange-specific price/OI/forced-flow series
without a predeclared matched venue rule.

`COORD-DISC-QUANT-003` must freeze exact squeeze, retention and deleveraging
definitions, sampling/matched controls, entry/stop/exit/hold, fixed cohort,
timeframe, chronological partitions, purging, costs, sample/stability gates
and total search breadth before outcome access. Preserve every protected
OOS interval across related research; a rolling data download must not turn
previously locked observations into new training data.

No squeeze strategy contract is falsely declared complete here. Once a
timestamp-defensible data path is established, freeze it and the full scientific
contract as a durable commit, then run only its authorized train/validation.
If feasibility fails, record that precise blocker and rank a genuinely distinct
available-data hypothesis before any outcomes; never fabricate forced flow.

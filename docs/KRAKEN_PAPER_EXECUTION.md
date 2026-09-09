# Kraken Pro paper execution contract

The paper account models Kraken Pro spot execution using public Kraken order-book depth only. It never places real orders and never uses private account endpoints.

Default fee assumption: Kraken Pro Spot Crypto Tier 1 taker fee, 0.80% per executed side (80 bps), based on Kraken's public fee schedule as of 2026-09-05. This is intentionally conservative until the actual account tier is independently verified. A lower tier fee must never be inferred from paper performance.

For crypto pairs where a stablecoin is only the quote currency (for example BTC/USDT), the normal spot crypto schedule applies. Stablecoin/FX base markets use the separate stablecoin/FX schedule; the current paper trading universe excludes stable bases.

Each simulated market fill walks the actual current Kraken public visible order book for the requested notional and computes full-size VWAP. Taker fees are embedded in the simulated fill price. If the Kraken pair is unavailable, the book request fails, or visible depth is insufficient, the paper trade/mark fails closed rather than using another venue or a candle/midpoint substitute.

The dashboard must continue to state that real execution is not verified. Existing legacy paper trades are never rewritten to pretend they used this model.

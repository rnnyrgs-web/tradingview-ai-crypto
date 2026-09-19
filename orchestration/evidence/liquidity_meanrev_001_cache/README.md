# First liquidity mean-reversion selection artifact

These are the first screen's immutable inputs and sealed evidence, preserved
before GitHub Actions artifact expiry. Source: run `35420353644`, artifact
`10577901325`, evaluated commit `e652d458401d40d45e098c85680ef96ddbd8ce51`.

- Original ZIP SHA-256: `085d46fabd899241e05865dd1bac39a9adf695ee68e1835203a9889080203df6`.
- Original dataset canonical SHA-256: `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`.
- Original evidence payload SHA-256: `8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e`.
- Contract SHA-256: `19252de4464fc997632b0500fded857bc58d5bdad49d6f72e3660eba75a28b57`.

`dataset.json.gz` is byte-for-byte the original compressed dataset;
`evidence.json.gz` losslessly compresses the original sealed JSON report.
The dataset includes an **opaque locked OOS tail**. Its storage, timestamp
validation and hashing are provenance operations, not permission to score it.
No OOS trade, return, regime or performance metric may be computed.

`python liquidity_mean_reversion_selection.py` replays only the original purged
train/validation intervals, verifies the entire selection object against the
first report, and fails on any mismatch. There is no network fallback or
fresh-history mode. All later workflow runs are engineering replays, not new
trials or independent evidence. No Supabase or market-data API is called.

`python liquidity_mean_reversion_audit.py --output PATH` computes descriptive
distribution/frequency statistics from the same original selection trades.
Those statistics cannot alter the frozen gates or rescue the rejected rule.

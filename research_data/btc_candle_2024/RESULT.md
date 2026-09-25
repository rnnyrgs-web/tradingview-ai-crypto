# BTC candle-clock replication: negative, unadmitted empirical evidence

Issue #806; draft PR #815. Fingerprint `EXT-BTC-CANDLE-CLOCK-001-v1`.

**Economic result: REJECTED_STAGE1. Canonical admission: NONE.**
This is an executed, locally predeclared historical development experiment,
not an admitted factory result, a profitable strategy or untouched OOS proof.
Both 2024 halves are now consumed. Do not retrofit pre-outcome approval,
change thresholds, reuse the validation half as fresh confirmation, or rescue
this candidate by selecting its best bucket. Broker/live trading remains OFF.

## Question and design

Do predictable 15-minute candle boundaries attract enough asymmetric buying
to produce a tradable return? The source mechanism is Shanaev, Vasenin and
Stepanov (2023), [Turn-of-the-candle effect in bitcoin returns](https://doi.org/10.1016/j.heliyon.2023.e14236).
This tests a post-publication translation to Binance BTCUSDT spot during
2024. It does not reproduce the paper's Bitfinex fee tiers or statistical model.

The primary rule buys at the open of minutes 0/15/30/45 and sells at the next
minute's open. The first half of 2024 is training and the second is chronological
validation. Round-trip costs are 24/48/72 bps; the base assumption is 20 bps fees
plus 4 bps spread/slippage. Prices are execution proxies, not actual fills.

Frozen controls use the same one-minute holding period: one-minute delay,
five-minute clock placebo, deterministic random offset 3–12 minutes, cash,
and a positive trailing-price baseline. Lagged aggressive-buy quote imbalance
uses only five completed minutes ending one minute before entry. Training-only
top 1/5/10/20/50% cutoffs are diagnostic score buckets, **not calibrated
confidence probabilities**. They cannot rescue a failed primary.

The original protocol was pushed at `3c9cbeb` before acquisition. Inference
clarification `c51db1b` and reviewed implementation/tail clarification
`e01fa57689bbc9cf5e614d64b4dda091a47ac2a0` also preceded acquisition. Main
advanced only by reviewer transport repair #797; it was reconciled before
scoring at `1d0a415a4ce4921f178dac36e9eebcc1b55c6920`, incorporating main
`1860f917c829ee5db4f4cd36404bf9702b6b680a`.

## Data and results

Twelve official monthly archives with filename-bound provider SHA-256 checksums
contained 527,040 one-minute rows. There were **35,135 complete matched events**:
17,471 training and 17,664 validation. No expected matched block was missing;
no zero-volume feature block was excluded. The first January boundary is
excluded by the frozen warmup. Exact raw source URLs, byte counts, hashes,
retrieval times and response metadata are retained in `evidence/manifest.json`.

All means below are basis points per selected trade, not NAV returns.

| Primary all-boundary result | Training | Validation |
|---|---:|---:|
| Gross mean | -0.0339 | +0.0558 |
| Net mean, 24 bps costs | -24.0339 | -23.9442 |
| Net mean, 72 bps costs | -72.0339 | -71.9442 |
| Clock placebo net mean, 24 bps | -24.1115 | -23.9064 |
| Random placebo net mean, 24 bps | -23.9176 | -23.9424 |
| Price baseline net per opportunity, 24 bps | -12.3773 | -12.0957 |
| Positive target-minus-clock complete weeks | 12 / 26 | 13 / 26 |
| Bonferroni-adjusted block-sign p | 1.0 | 1.0 |

Cash earns zero. The price baseline abstains on negative lagged price momentum;
its denominator includes those cash opportunities. Validation target-minus-clock
gross advantage is **-0.0378 bps**. Q3 and Q4 net means are -23.8860 and
-24.0024 bps respectively at base costs. Cost, profit-factor, tail/winner,
baseline/placebo and adjusted-inference gates failed. No expensive validation
or additional outcome interval was opened.

| Training score bucket | Training n | Validation n | Validation coverage | Validation gross bps | Validation net bps, 24 cost |
|---|---:|---:|---:|---:|---:|
| Top 1% | 175 | 293 | 1.66% | +0.2233 | -23.7767 |
| Top 5% | 874 | 1,058 | 5.99% | -0.2034 | -24.2034 |
| Top 10% | 1,748 | 2,079 | 11.77% | -0.0618 | -24.0618 |
| Top 20% | 3,495 | 3,663 | 20.74% | -0.0765 | -24.0765 |
| Top 50% | 8,736 | 8,030 | 45.46% | -0.1300 | -24.1300 |
| All | 17,471 | 17,664 | 100% | +0.0558 | -23.9442 |

Every nonempty bucket loses after costs in both halves. The top-1% validation
clock contrast has raw p=0.03776 but adjusted p=0.45311 across the twelve
predeclared half/bucket tests; this is neither economic nor statistical rescue.
Complete nonzero weekly blocks, not trade rows, are the inferential units.
The final two validation days contribute to economics but not the weekly test.
Serial dependence can still invalidate independent-sign assumptions.

## Causal interpretation and decision

The proposed initiating driver was scheduled candle-processing demand, with
lagged aggressive buying as an amplifier. Same-minute order flow was excluded
as a potential consequence. Off-boundary controls test clock specificity.
The results provide no useful incremental clock advantage or viable selective
subset under this execution/cost translation. They do not identify trader
intent or disprove every version of the published mechanism. Macro liquidity,
whales, news, depth withdrawal and cross-asset rotation were not measured and
receive no causal attribution.

Preserve this exact candidate's negative result; no retuning or lower-cost
reinterpretation. The practical lesson is to demand a mechanism whose expected
gross return can plausibly exceed our executable costs before investing in a
short-horizon replication. Neither this family nor the previously rejected
liquidity-selectivity family should consume another validation cycle.

## Admission finding and evidence limits

After scoring, another task (#814) asserted a universal requirement for
canonical admission before independent screens. An independent read-only
review checked current main: `validate_predeclaration` is explicitly a
cheap-screen **research** admission contract, and new canonical executable
shapes require reviewed schema changes. This experiment did not pass it or
receive a canonical exact-head admission receipt. Its local pre-outcome review
and green CI do not substitute for those gates.

The reviewer did not find an explicit current-main rule requiring every
standalone empirical diagnostic to enter that contract. The scope remains
unresolved; do not claim either canonical permission or a proven universal
policy violation. Preserve these already-opened results as **unadmitted
empirical negative evidence**. Before any further independent strategy screen,
the Lead must resolve that boundary in authoritative state. No schema or gate
is being weakened, and no post-outcome approval can make these outcomes unread.

Historical archives retrieved now can contain revisions. Checksums bind bytes,
not historical publication time; this is not a canonical PIT-vintage acquisition
attestation. The fixed BTC market avoids cross-sectional survivor selection but
does not certify fillability or source availability at each historical decision.

## Retained evidence and verification

- `evidence/events.json.gz`: all matched event features and target/control returns;
  decompressed JSON SHA-256
  `a5c3ebe8e5799af419bb2f95411ad29c8fde406887680ee55ed2b3ec90d6ee91`.
- `evidence/manifest.json`: canonical JSON SHA-256
  `8fdc4140ce20dfba70bcbbd84312fb91154c1c2535b5e90d9a8b6c17628ccae6`.
- `evidence/result.json`: original once-executed full output, including all
  costs, controls, buckets, failures and authority flags; preserved unchanged.
- `evidence/consumption.json`: append-only classification of this opened sample.
- Raw archives and provider checksums remain in the local `.candle-cache-2024`
  directory. They are not committed. Reacquisition would need to match the
  recorded hashes; a provider revision is not interchangeable.
- Seventeen focused synthetic tests passed before acquisition and after main
  reconciliation. Exact implementation head `1d0a415` passed Security and
  Reliability run `36078670927`. Final artifact-head CI is reported on PR #815.

## Next highest-information experiment

The existing ETH Tuesday replication #790 is the closest owned, frozen
experiment to a legitimate new economic result; #810's gate repair has been
integrated into its branch. Its owner must complete exact-head CI, independent
scientific review and execution admission before opening the existing sample.
Do not duplicate that owner. The parallel 2x historical supply census #812 is
also owned; canonical event/control labels remain blocked on PIT coverage.
No fresh profitable strategy or authentic 90-day 2x candidate is established.

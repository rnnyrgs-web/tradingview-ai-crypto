# Does stronger liquidity-shock intensity improve the rejected reversal rule?

## Finding

**Every nonempty validation bucket has negative mean trade-label returns even
at the original 20 bps base cost.** The strongest 1% training threshold admits
zero validation trades; the 5% threshold admits only two. This diagnostic
provides no basis to rescue `DISC-LIQUIDITY-MEANREV-001-v1` or select a bucket
for trading. The strategy stays rejected and NO TRADE.

| Training top bucket | Training labels | Training mean net bps, 20 cost | Validation labels | Validation coverage | Validation mean net bps, 20 cost | Validation mean net bps, 60 cost |
|---|---:|---:|---:|---:|---:|---:|
| 1% | 5 | -154.18 | 0 | 0% | unavailable | unavailable |
| 5% | 22 | -50.36 | 2 | 1.63% | -11.90 | -51.90 |
| 10% | 43 | -34.14 | 9 | 7.32% | -24.07 | -64.07 |
| 20% | 85 | -14.80 | 35 | 28.46% | -5.23 | -45.23 |
| 50% | 213 | -48.08 | 88 | 71.54% | -18.17 | -58.17 |
| All labels | 425 | -48.87 | 123 | 100% | -5.48 | -45.48 |

The full baseline's validation gross mean is +14.52 bps, below the 20 bps
cost assumption. For this intensity proxy, stricter filtering does not reveal
an observed positive after-cost subset among the fixed requested buckets.
This does **not** prove that every possible selective rule fails, nor that
genuine microstructure features lack predictive value.

## Method and evidence boundary

- Score: `abs(shock_return) / trailing_sigma`, already present at formation
  in the frozen experiment. It measures shock intensity, **not calibrated
  confidence**, expected return, or certainty of reversal.
- One score and buckets 1/5/10/20/50% plus the full baseline were specified in
  issue [#799](https://github.com/rnnyrgs-web/tradingview-ai-crypto/issues/799)
  before this calculation. Original experiment outcomes were already known:
  this remains a **post-selection descriptive diagnostic**, not predeclared
  confirmation, a new independent experiment, or out-of-sample evidence.
- For each percentage, take the `ceil(n_train * percentage / 100)`-th largest
  training score. Include every tie. Apply that same numeric cutoff to
  validation. Validation is never independently ranked or used to fit cutoffs.
  Actual validation coverage therefore differs from the training percentage.
- Costs remain the original 20/30/40/60 bps assumptions. They are not observed
  historical executable quotes, spread, funding, slippage, or capacity evidence.
- These are equal-weight trade-label means, not portfolio returns. Nested
  buckets share observations; simultaneous assets and adjacent holding periods
  can be dependent. The full 123-label validation sample comprises 77 signal
  hours and 66 disjoint holding-interval clusters; even those clusters are not
  proven statistically independent. No significance or confidence interval is
  asserted, especially for the two- and nine-label buckets.
- The subsets contain only originally executed labels. The original rule
  skipped signals while holding; filtering entries could admit other later
  signals. This is not a replay of a selective trading policy.
- The loader reads only the original sealed `evidence.json.gz`, verifies its
  envelope and pinned payload SHA-256, and extracts training/validation trade
  lists. It never opens `dataset.json.gz`, fetches market data, or scores
  protected OOS/forward observations. Re-signing modified evidence is rejected.

Original source: run `35420353644`, artifact `10577901325`.
Payload SHA-256:
`8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e`.
The unchanged original contract is
`19252de4464fc997632b0500fded857bc58d5bdad49d6f72e3660eba75a28b57`.
See the original [postmortem](liquidity_meanrev_001_audit_20260919.md).

## Reproduction

```powershell
python liquidity_selectivity_postmortem.py --output docs/research/evidence/liquidity_selectivity_20260924.json
python -m pytest -q tests/test_liquidity_selectivity_postmortem.py
```

The [machine-readable report](evidence/liquidity_selectivity_20260924.json)
contains every cutoff, all four cost assumptions, counts, coverage, win rates,
overlap diagnostics, source identity, and authority restrictions. Empty means
remain null. Replaying this artifact adds no independent evidence.

## Research decision

Retain the rejection and the existing materially distinct research queue.
Do not add thresholds, choose a best bucket, mutate parameters, or spend deep
validation capacity on this rejected family on the strength of this analysis.
The next useful evidence is the existing owner's frozen Stage-1 screen after
its review/data gates clear. This slice adds no 2x event/control population,
precursor validation, candidate, causal finding, or profitable strategy.
Broker, trading, promotion and integration authority remain NONE.

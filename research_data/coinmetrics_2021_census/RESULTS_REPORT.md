# Results mission — 2026-09-24

**Outcome: no strategy edge or 2x predictor was established.** A complete,
reproducible historical source-coverage census replaced the previous one-asset
probe with actual measurements. The ETH Tuesday outcome remains sealed because
its independent admission boundary has not been satisfied. This mission did
not achieve the requested economic-result objective; these are bounded data
results and a verified admission-repair review, not profitability evidence.

## Strategy factory

| Item | Verified state |
|---|---|
| Priority fingerprint | `EXT-ETH-TUESDAY-DRIFT-001-v1` |
| Mechanism | Published ETH Tuesday weekday drift, translated to a fixed UTC perpetual session |
| Frozen dataset | OKX ETH-USDT-SWAP 1H; normalized SHA256 `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f` |
| Frozen screen window | 2025-05-12 through 2026-08-30; 68 scheduled weeks, 34 per half |
| Frozen round-trip costs | 24 / 48 / 72 bps; 48-bps primary gate |
| Real strategy hypotheses tested this run | **0** |
| Real trades/events scored | **0** |
| Gross/net expectancy, PF, win/loss, drawdown, halves/regimes, concentration and cost sensitivities | **NOT MEASURED — sealed**, not zero returns |
| Baselines/ablations and frozen falsifiers | Not executed on real data |
| New terminal strategy rejections | None; a review blocker is not a scientific rejection |
| Strongest surviving strategy | None established; Tuesday remains an untested candidate |
| Evidence level | Level 0 for this candidate; no new evidence of economic edge |

At inspection, #790 head `20a8b685ceacf11a46df61c69b49154e606dd079`
had successful Security and Reliability run `36032880614`, but no legitimate
exact-head scientific admission. Repair #810 head
`78c97f61b1c62f663b62ac4215821227d5532a65` remained open and unintegrated.
Its public entrypoints now unconditionally reject pre-admission execution.
I independently reviewed its five-file diff and ran all **43 focused tests**,
which passed. Bounded review is recorded as GitHub review **5311572394**.
It is a read-only COMMENT, not a canonical multi-review receipt or runtime token.

The exact #810 head had **zero Actions runs**. Existing `security.yml` triggers
automatic PR CI only for base `main`; this child targets the #790 branch.
The existing manual workflow can test that branch without new infrastructure.
This session's connector cannot dispatch a workflow, and its browser was signed
out, so no remote CI dispatch or integration was performed. No automatic approval
review rejected an action; this is an unavailable authenticated dispatch path.

Next gate: exact-head CI and legitimate separate integration/review of #810 into
#790, fresh #790 independent admission, then the separately reviewed exact-identity
admission change. Only after that boundary is satisfied may Stage 1 execute.
Original pre-screen source-content authenticity remains unresolved for any positive
external-replication claim. No outcome was opened to work around either blocker.
Existing BTC candle-clock issue #806 was left to its active owner.

## 2x factory: empirical data availability

Task **#812** implements the existing merged source-feasibility request under
#505/#514. The denominator was frozen before source-value inspection in GitHub
commit `991792f21f0e05b14f70f49722e0af0f80eb5630`: **every one of the 100 asset
CSV files** in original upstream `coinmetrics/data` commit
`25e3b1d90ffddef11c1663f8fa43696f60bc8061`, excluding only `csv/metrics.csv`,
the metric dictionary. No today's-survivor filter was used. Source-symbol names
are not assumed to be distinct canonical assets or historical Binance members.

The fixed decision cutoff is **2021-01-04 00:00 UTC**. Only date,
`CapMrktCurUSD` and `SplyCur` were interpreted numerically. The parser does not
calculate price returns, forward outcomes, 2x labels, rankings or matched controls.
The <=72-hour freshness statistic is descriptive, not a changed admission rule.

| Measured quantity | Result |
|---|---:|
| Frozen files acquired and exact-Git-blob verified | 100 / 100 |
| Acquisition/parse failures | 0 |
| Raw source bytes verified | 58,065,298 |
| Daily rows strictly before cutoff | 116,831 |
| Rows at/after cutoff | 0 |
| Daily rows with both metrics finite and positive | 102,425 |
| Files containing both columns | 97 |
| Files with a fresh latest positive pair | 91 |
| Latest-row cap: positive / missing value / missing column | 95 / 2 / 3 |
| Latest-row supply: positive / missing value / missing column | 96 / 2 / 2 |
| Files whose latest row is older than 72 hours | 4 |
| Canonically admitted Cohort-001 snapshots | **0** |

All nine nonpassing latest records are preserved:

| Source symbol | Latest pre-cutoff row | Reason |
|---|---|---|
| bnb | 2019-04-22 | Stale legacy series |
| bnb_mainnet | 2021-01-02 | Both values missing |
| eos | 2021-01-02 | Both columns missing |
| eos_eth | 2018-06-02 | Stale legacy series |
| kcs | 2021-01-02 | Market-cap column missing |
| sai | 2019-11-30 | Stale series |
| trx | 2021-01-02 | Both columns missing |
| trx_eth | 2018-06-25 | Stale legacy series |
| tusd | 2021-01-02 | Both values missing |

**FACT:** free immutable upstream blobs contain substantially broader supply/cap
coverage than the earlier BTC-only probe established. Column availability is not
enough: 97 files have both columns but only 91 pass the frozen descriptive latest
pair/freshness check. A naive present-day ticker splice or last-known-value fill
would hide the migration/staleness and missingness cases above.

**INFERENCE:** this source is worth qualifying for historical supply/cap inputs;
buying another data feed solely because all such free coverage is assumed absent
is not justified by this measurement. No spending recommendation or authorization
is created.

**UNKNOWN:** historical public availability of the unsigned Git objects, source
revision chronology, economic supply semantics, canonical identity continuity,
historical Binance membership, liquidity, sector and executable depth/spread.
The one source vintage is not 52 weekly PIT snapshots, and its earlier daily rows
may be revised. Stablecoins/wrappers/obsolete symbols remain in the census; 91
source files cannot be called 91 eligible trading assets. Daily rows are neither
independent events nor independent forecasts.

| Required economic output | This run |
|---|---|
| Historical 2x events generated | **0** |
| Outcome-blind matched controls generated | **0** |
| Precursor hypotheses tested | **0** |
| Base rate, lift, precision@K, PR-AUC, prospective return, MAE, false-positive rate | **NOT ESTIMABLE** |
| Strongest precursor evidence | None tested |
| Qualified current prospective candidates | **0 — NO QUALIFIED CURRENT 2X CANDIDATE** |

The existing `SEALED_UNTIL_COVERAGE_READY` boundary was preserved. Missing or
unauthenticated membership and tradability evidence was not replaced with these
source-coverage observations. No failed asset or missing observation was labeled a
non-winner, and no current recommendation was formed.

## Reproduction and validation

From repository root, acquire the exact pinned upstream files, or replay offline
after extracting the retained source archive into this directory:

```sh
python research_data/coinmetrics_2021_census/run_census.py --acquire
python research_data/coinmetrics_2021_census/run_census.py
PYTHONPATH=. python -m pytest -q tests/test_coinmetrics_2021_census.py
```

The first command downloads only missing raw files; every run verifies their exact
size and upstream Git blob identity before parsing. Default execution is offline.
Every failure remains in `results.json`; no silent denominator reduction is allowed.
The full per-file metric values/missingness and SHA256 identities are in that file.

- Results SHA256: `d6584f06b39c3a4869ac6593130102cf622e14f08f6c8343e334e36a64a5224f`.
- Offline replay reproduced that exact hash.
- Synthetic parser/hash/cutoff tests: **12 passed** after a 12-failure RED run.
- Full applicable repository suite: **1,862 passed, 2 skipped** in 51.72 seconds.
- Initial collection errors were local missing dependencies; installed the existing
  requirements and `socksio` for this runtime's proxy, with no repository dependency edits.
- Separate read-only review found no concrete defect, independently reconstructed
  the pinned source tree, and verified every retained blob/per-file result. This
  local review does not substitute for canonical external scientific admission.
- `git diff` verified the local frozen manifest/tree match the remote pre-inspection
  commit. Base main stayed `55e3ad02c3f050510c621cc04616c1112fe2b4a6`.

Retained exact originals: `coinmetrics-2021-source-bytes.tar`, 26,337,280 bytes,
SHA256 `74a240975256122a164936ba3f1378837299a826fdf38b5dd62afbcad5472067`.
Persistent artifact ID: `libfile_855ee5fe26e881919cda88e0747b2462`.
Its `raw/*.csv.gz` decompress to all 100 exact upstream blobs. The source commit,
tree, retrieval URLs and blob IDs are also retained in this PR, so acquisition is
reproducible without depending on the original working directory. This archive is
quarantined evidence, not an approved trusted-acquisition attestation.

## Engineering and next action

Only a standalone deterministic measurement script and its tests were added. No
production worker, schema, routing, dashboard, rejected registry or research gate
was changed. No new paid data, broker connection or real trading was authorized.

**Single highest-value next action:** dispatch the existing Security and Reliability
workflow on `review/pr790-stage1-admission-gate`, verify exact SHA
`78c97f61b1c62f663b62ac4215821227d5532a65`, and complete the legitimate #810 -> #790
admission sequence. That is the shortest path to the requested numerical strategy
test; adding another architecture layer is not required.

This run removed uncertainty about free historical supply/cap coverage and
identified the concrete absent-CI cause. It removed **no measured uncertainty about
after-cost strategy profitability or 2x precursor lift**; those outcome tests did
not legitimately run.

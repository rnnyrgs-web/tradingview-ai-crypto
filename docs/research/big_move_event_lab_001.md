# BIG-MOVE-EVENT-LAB-001 — event/control foundation

User-assigned independent Work implementation, based on main
`f62db7c45db2ee442dbc6bf4031c9559168bd46d`. No takeover of active
DATA-004 / TEST-003 or changes to their queues. Branch: `agent/big-move-event-lab`.

## Scientific and implementation contract

The canonical target is **2X_PLUS_EVENT_90D**: a liquid asset's observed
price reaches at least twice its decision-time price within the following
90 calendar days. Larger moves count without a cap. Record 30/60/90-day
maximum and endpoint returns, maximum multiple, cumulative 2/3/5/10x
indicators, threshold arrival intervals and pre-threshold drawdown limits.

This milestone accepts normalized, explicitly sourced UTC OHLC bars and
point-in-time universe snapshots from local files. It does not acquire data,
inspect protected strategy OOS, estimate probabilities, discover precursors,
or activate a trading/promotion path. Historical provenance in the input is
an assertion requiring independent source audit, not proof supplied by this
builder. Only a declared DEVELOPMENT partition is accepted.

Snapshots include per-field observation/availability timestamps and source
references for price, liquidity, market cap, float, listing age, sector,
volatility, recent return, BTC regime and tradability. Require observation <=
availability <= decision, bounded staleness, and explicit eligible membership.
Keep ineligible rows with reasons. Never filter by future survival. For the
same asset, select decision windows chronologically at least 90 days apart,
before labels, retaining excluded overlapping rows in the audit table.

OHLC interval starts must be at/after the decision. Exact cadence and full
horizon coverage are required to establish a negative label or complete
maximum. Missing, immature, or not-yet-available history is CENSORED, never a
non-winner. Preserve observed positive threshold lower bounds separately.
Duplicate, malformed, nonfinite, and off-grid bars are input errors.

OHLC highs establish threshold reach, not executable fills. Arrival time is
an interval, with `days_to_Nx` explicitly the bar-end upper bound. Exact
intrabar maximum drawdown is UNKNOWN; preserve completed-close sampled
drawdown strictly before the crossing bar, with that limitation in its name.

Matching first builds a fixed nearest-neighbor pool for **every** eligible
non-overlapping snapshot, without access to labels. Require the same decision
time, venue, sector and BTC regime; fixed per-covariate absolute calipers and
L1 scaled distance; asset-id tie-break. Freeze/hash all pools before labeling.
Only then select observed complete non-winners from each winner's fixed pool.
Do not refill from farther assets based on outcomes. Report insufficient
controls and candidate outcomes/unknowns explicitly. Controls may be reused;
reuse counts are reported, and pair rows are never independent sample counts.
Cross-asset/date dependence still requires clustered inference downstream.

The contract and actual normalized input tables receive SHA-256 digests.
Callers supply the independently retained expected contract digest; mutation
fails closed. The digest does not by itself prove pre-outcome registration.
Output is a new immutable directory of compressed canonical JSONL tables plus
manifest, optionally Parquet when pyarrow is already available. No Supabase
reads/writes, paid API, workflow permission, or runtime dependency changes.

## DONE and execution plan

1. Write failing behavior tests for uncapped labels, calendar boundaries,
   censoring, PIT/freshness, malformed data, overlap, and outcome-blind pools.
2. Implement `big_move_lab/core.py` validation/labels and
   `big_move_lab/matching.py` deterministic matching. Run focused tests.
3. Add test-first `big_move_lab/artifacts.py` and `__main__.py`: local CLI,
   canonical hashes, immutable compressed tables, optional Parquet and manifest.
4. Run the full applicable suite, security checks, independent review; publish
   the exact tested tree in an isolated PR and verify exact-head CI.

Review focus: censored/delisted controls; bars straddling the decision/horizon;
post-decision metadata; same-asset overlap and cross-case reuse; dataset and
contract tampering. These require behavioral regressions, not text assertions.

## Next dependent milestone

Independently audit and freeze a survivorship-safe historical DEVELOPMENT
universe and source manifest, then run this builder. Freeze precursor
hypotheses/search breadth before opening those new outcomes. Add chronological
base-rate/lift/top-percentile metrics only on the full eligible cohort, never
on outcome-enriched matched pairs. Current ranking, provider ablations,
watchdog/scorecard and narrowly authorized Trusted Lead integration are later
milestones; this PR does not claim they are active.

## Running the builder

Prepare two local JSON files. The input object has exactly `snapshots` and
`bars` arrays. `tests/test_big_move_event_lab.py` contains complete synthetic
schema examples; those fixtures are engineering checks, not research results.

Each snapshot has `asset_id` (stable underlying-asset identity, not a recycled
ticker), `venue`, `decision_time`, and `features`. Each feature has exactly
`value`, `observed_at`, `available_at`, `source`. Required features are `price`,
`liquidity_usd`, `market_cap_usd`, `float_supply`, `listing_age_days`,
`volatility_30d`, `return_30d`, `sector`, `regime`, `tradable`, and `member`.
The price must be observed exactly at the decision. Source is the identifier
of the independently audited normalized PIT snapshot, which must retain its
upstream provenance externally. Missing information cannot be filled with a
plausible value just to satisfy the schema.

Each bar has exactly `asset_id`, `venue`, `start`, `end`, `available_at`,
`open`, `high`, `low`, `close`, `source`. Bars must use consistent, independently
audited adjusted-price/token-denomination semantics across the entire period.
Hourly and daily UTC grids are supported; cross-market exchange calendars and
corporate-action normalization require their own future contracts.

The contract schema is explicit in `validate_contract` and the test fixture.
`partition_start/end` bound all supplied prices and every decision's full
90-day horizon. Source IDs identify normalized input artifacts, not provider
marketing names. Units: USD market cap/liquidity, asset units of float, days
of listing age, decimal 30-day return and realized volatility. Freeze the
liquidity measurement window, volatility estimator, regime/sector mapping,
listing policy, raw source hashes and receipt/publication evidence in the
upstream source manifest before this contract is used on real observations.
The builder does not derive or certify those covariates.

```bash
python -m big_move_lab --contract audited-contract.json \
  --expected-contract-sha256 "$FROZEN_CONTRACT_SHA256" \
  --input development-input.json --as-of 2026-09-19T00:00:00Z \
  --output /path/to/new-event-dataset
```

The expected contract hash must come from the earlier reviewed declaration,
not a recalculation that silently accepts changed rules. Add `--parquet` only
when pyarrow is already available in the research environment; no production
dependency or subscription is added. Core operation uses only Python stdlib.
100 MiB input/table bounds make this a bounded batch tool, not yet a streaming
data lake. Preserve source inputs and their manifests alongside the output in
approved cold storage. The manifest binds actual normalized input hashes and
output table hashes. Verify with:

```python
from big_move_lab.artifacts import verify_bundle
dataset = verify_bundle("/path/to/new-event-dataset",
                        expected_dataset_hash=independently_retained_dataset_hash)
```

Output tables: every snapshot and eligibility decision; outcome-blind matching
pools; complete/censored labels; event matching status; control pairs and reuse
counts. A `manifest.json` written last marks completion. Existing directories
are never overwritten. A partial directory after interruption is not evidence;
retain it for diagnosis and retry at a new output path.

Synthetic checks do not establish a predictive edge, a historical event count,
or a current candidate. A gap/delisting may leave censoring informative;
therefore full-cohort base rate is suppressed whenever any label is censored,
and even the reported complete-case rate carries a survival-bias warning.

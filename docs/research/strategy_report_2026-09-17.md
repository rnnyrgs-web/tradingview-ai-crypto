# Strategy evidence report — 2026-09-17

## Decision

**NO VALIDATED STRATEGY. WAIT / RESEARCH_ONLY.**

Canonical main: `dfa71d64d0faf6581392a19a5ef6a929ee8aa12f`.
Phase: `SELECTION`; active strategy fingerprint: **none**.
The latest focused worker report contains **0 hypotheses evaluated, 0 validation
passes, 1 blocked screen, and 0 untouched-OOS openings**. Repeated worker cycles
are not independent experiments or additional scientific evidence.

This report is a Lead coordination/evidence audit, not a new profitable backtest.
The bounded live evidence is preserved in
[`evidence/2026-09-17_strategy_snapshot.json`](evidence/2026-09-17_strategy_snapshot.json).

## Focused strategy screen

- Existing hypothesis family: ACC-002, volatility-normalized cross-sectional
  relative strength, 24-hour outcomes from completed 1-hour OKX spot candles.
- Latest worker result: **2026-09-17 11:42:36 UTC**.
- Requested dataset: current Top-30 liquid universe, 3,000 hourly bars per asset.
  Only 24 assets supplied sufficient history. Top-15 coverage was **11/15**,
  below the unchanged minimum **12/15**; Top-30 was **24/30**, meeting its minimum.
  Two supported liquidity subsets are required; only one was available.
- Result: `insufficient_supported_liquidity_subsets`, before candidate scoring.
  No new candidate fingerprint was produced. Evidence-envelope SHA-256:
  `757e38f0dfb4fe91efae37e650347c4f771538509522f7f9d3a930ce4852211e`.
  This is an **artifact hash, not a strategy fingerprint or dataset hash**.
- Existing declared lookback grid: `(4,16,64)`, `(6,24,72)`, `(8,32,96)` hours.
  None was evaluated in this blocked screen. Do not count them as tested today.
- Model costs: 12 bps aggregate round-trip deduction, stressed at 1x/1.5x/2x/3x
  (12/18/24/36 bps). This simplified research spread model is not proof of
  executable Kraken fees, borrow/funding, market impact or historical bid/ask fills.
- Chronology: existing purged 60/20/20 split and non-overlapping 24-hour sampling;
  train/validation metrics **unavailable for this blocked run**; OOS **unopened**;
  candidate-specific forward metrics **unavailable**.
- Exact dataset start/end, full immutable snapshot and dataset hash are **not
  exposed by the live summary**. Do not infer dates from a requested bar count.
  The point-in-time universe manifest is also unconfigured; the screen reports
  71,976 uncovered observations and `promotion_allowed=false`.
- A single local public-OKX connectivity probe timed out after 20 seconds. No
  substitute data, survivor reconstruction, fresh OOS run or source rotation was
  attempted to manufacture a result.

DATA-BREADTH-001 / COORD-DATA-007 remains blocked awaiting prospective mature
point-in-time evidence. Its required independent 24h/7d cohort counts were not
freshly verified in this audit. No replacement data candidate was started.

## Rejections remain permanent

These are prior results from the canonical rejected-fingerprint registry, not
new tests today. Neither fingerprint was rerun or renamed.

| Exact fingerprint | Existing evidence | Decision |
| --- | --- | --- |
| `DATA-BASIS-001`, version 1 | 8,000-hour window; 24h OOS n=134, mean net −8.490253160921695 bps; 7d n=19, −51.210226000078 bps | Rejected |
| `DATA-FUNDING-001`, version 1 | 24h OOS n=38, +43.56917973482839 bps but **0 incremental** vs frozen baseline; OOS halves +91.54259508197315 / −4.404235612316374 bps; 7d n=6 < required 8 | Rejected |

## Genuine paper results are not candidate proof

Production `/health` checked at approximately **15:29 UTC** reported the authentic
$100,000 baseline ledger: equity **$96,594.40**, return **−3.406%**, realized P&L
**−$3,728.24**, **28 closed trades**, **9 wins / 19 losses**, profit factor
**0.648**, maximum drawdown **8.408%**, and 4 open paper positions.
Reconciliation was `LEDGER_VERIFIED`; execution authenticity remained
`PARTIAL_LEGACY_HISTORY` with 9 legacy rows. These are mixed legacy paper-account
results, **not forward validation for an immutable active strategy**.
`consistently_profitable=false`, `real_money=false`, and broker/trade authority
remained false. No ledger reset or rewrite occurred.

## Concrete work completed and persistent-worker truth

1. Verified #385 (one-strategy focus) and #386 (Mission Control) are merged.
   Current-main Security and Reliability
   [run 35160596874](https://github.com/rnnyrgs-web/tradingview-ai-crypto/actions/runs/35160596874)
   passed on exact SHA `dfa71d6`.
2. The public coordinator health snapshot at **15:31 UTC** was healthy and showed
   **one heavy selection worker plus two lightweight diagnostic/factory workers**.
   Public health does not expose its deployed Git SHA; exact Render deployment
   identity was not independently verified because no workspace was selected in
   the connector. Health and exact-code deployment are separate claims.
3. Independent read-only review confirmed `.github/workflows/cloud_research.yml`
   bypasses the focused worker selector. Its 5 fast-evidence jobs and 17 research
   shards invoke `research_runner.py` without the candidate contract; absent deep
   mode, that runner evaluates all families and opens unrelated OOS. A fresh
   [cloud run](https://github.com/rnnyrgs-web/tradingview-ai-crypto/actions/runs/35233315349)
   confirms that path still executes on current main.
4. Prepared a **workflow-only quarantine** of those two legacy matrices. Downstream
   audit/aggregation jobs then skip automatically. The focused Render worker,
   collection, scan, safety CI and scientific gates are unchanged. This is
   proposed containment, **not deployed until reviewed integration**; it does not
   cancel already-started runs. It changes no production or test Python code.
5. Claude research's latest paid attempt at **04:26–04:27 UTC** returned `BLOCKED`
   for COORD-VAL-001. Its **15:26 UTC** workflow was successful only because the
   model step correctly skipped during cooldown. The durable state does not
   preserve the detailed BLOCKED reason; do not invent one from its older
   `paused_reason=MODEL_EXECUTION_FAILURE` field.
6. Claude Code has **six recorded failed attempts** for COORD-TEST-001 and is
   paused at `TASK_RETRY_LIMIT`; its latest checked plan returned
   `STALE_MAIN_WITH_ACTIVE_TASK`. No retry counter, budget guard or stale claim was
   silently reset, and no paid retry was dispatched.
7. Draft [PR #387](https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/387)
   remains unmerged at `613b28321bed29a36376db36b34c5d29ab8e0c2d`.
   Exact-head [Security and Reliability run 35170245264](https://github.com/rnnyrgs-web/tradingview-ai-crypto/actions/runs/35170245264)
   passed; its own audit reports 916 local tests passing. Its scientific audit
   nevertheless blocks deployment on candidate-wide robustness aggregation,
   actual frozen independent-reproduction inputs, and the authoritative forward
   opportunity producer. The audit also records a database access-control review
   item. None was waived. The runner-level correction overlaps #387; this
   quarantine intentionally does not edit that runner.

## Budget

The three durable specialist ledgers record **$2.382791** for September:
ChatGPT specialist $0.582400, Claude research $0.600391, Claude Code $1.200000.
Today's recorded specialist usage is **$0.042131**. Failed calls include
conservative reserved charges; the fetched fleet ledger had no pending reservations.
These figures do **not** verify provider invoices, all review/production AI calls,
GitHub runner charges, or infrastructure. Do not report $27.62 as verified
remaining project budget. The shared **$30/month ceiling remains unchanged**.

## One highest-value next action

Integrate the minimal legacy-workflow quarantine after exact-head CI and Lead
review. This stops repeated unrelated OOS work while preserving the one permitted
screen. Its bounded follow-through is to obtain the missing-history provenance
and immutable, timestamped dataset needed for ACC-002's existing pre-OOS test,
without lowering 80% coverage, backfilling membership or choosing parameters from
holdout outcomes. Claude should falsify the frozen economic/cost contract; Claude
Code should implement only the claimed bounded blocker once its stale failed
claim is safely reconciled. No new UI, indicators, infrastructure, or parallel
deep candidates are prerequisites for this next action.

Sources: current-main `AI_STATE.md`, canonical coordination plus overrides,
`orchestration/rejected_fingerprints.json`, `cross_asset_runner.py`,
`cross_asset_rank.py`, the linked Actions/PR evidence, durable engine-state files,
and read-only production/coordinator health snapshots.

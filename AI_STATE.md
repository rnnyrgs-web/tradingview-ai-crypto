# AI_STATE.md

Last reconciled: 2026-09-19T04:31Z
Last updated: 2026-09-19T04:31Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. On every run, first read current default-branch `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `docs/MULTI_ENGINE_PROTOCOL.md`, `SIGNAL_BACKTEST_CHARTS_SPEC.md`, the strategy-discovery queue, rejected-fingerprint registry, specialist coordination plus overrides, and actual GitHub/runtime evidence. GitHub/persistent machine-readable state outranks chat memory and stale branch notes.

## PRIMARY OBJECTIVE

Find and rigorously validate **one genuinely working algorithmic strategy** with sustainable positive after-cost expectancy and useful frequency, then determine defensibly which assets/markets/timeframes it responds to without data-mining.

Exactly one candidate may consume expensive deep-validation capacity at a time. Cheap predeclared screening may reject many candidates. A rejection is a state transition: **FAIL -> EXPLAIN -> LEARN -> RECORD -> PIVOT -> CONTINUE**.

Do not call backtests real profit. Do not weaken chronology, OOS, multiple-testing, cost, provenance, robustness, or forward-evidence gates to manufacture success. Never suppress a genuine pass that actually satisfies the frozen gates.

## CURRENT CANONICAL RESEARCH STATE

- No validated profitable strategy exists yet.
- Discovery lifecycle remains **SELECTION**; `active_deep_candidate` remains `null`.
- Broker/live authority remains **OFF**. Research/paper/shadow only.
- Combined variable paid-project ceiling remains approximately **$30/month total** unless explicitly changed by the user.
- `main` is not branch-protected; isolated branches and exact-head Security & Reliability are mandatory before merge.
- Untouched OOS must remain locked until an exact frozen selection candidate legitimately passes and is centrally advanced.

### Newly closed candidate: `DISC-LIQUIDITY-MEANREV-001-v1`

The frozen selection-only screen completed on PR #416 evidence head `e652d458401d40d45e098c85680ef96ddbd8ce51` and **failed pre-OOS**.

Frozen contract:
- fixed BTC/ETH/SOL OKX USDT perpetuals;
- 1H bars;
- large return shock > both 1.5% and 2x trailing 168H sigma;
- quote-volume ratio >= 1.5 and range ratio >= 1.5 versus trailing medians;
- opposite-direction next-open entry;
- fixed six-hour hold;
- 20 bps round-trip proxy stressed through 3x;
- 60/20/20 train/validation/untouched-OOS chronology with purge;
- no asset/timeframe optimization; two non-selectable sigma falsifier sensitivities.

Exact selection evidence:
- workflow run: `35420353644`;
- artifact: `10577901325`;
- artifact digest: `sha256:085d46fabd899241e05865dd1bac39a9adf695ee68e1835203a9889080203df6`;
- dataset: 35,997 normalized rows, 2025-05-07T05:00Z through 2026-09-19T03:00Z;
- dataset SHA-256: `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`;
- data integrity: PASS;
- passing fixed instruments: **0/3**;
- pooled train, 3x costs: 425 trades, mean net **-88.87 bps**, PF **0.331**;
- pooled validation, 3x costs: 123 trades, mean net **-45.48 bps**, PF **0.456**;
- baseline validation, 3x costs: mean net **-47.07 bps**;
- validation halves: **-29.15 bps / -63.77 bps**;
- BTC / ETH / SOL validation means: **-50.83 / -46.73 / -41.63 bps**;
- sigma 1.75 and 2.25 falsifier sensitivities both failed with negative train and validation expectancy;
- untouched OOS: **LOCKED / unopened**;
- genuine forward: not opened.

Interpretation: the liquidity filters slightly improved validation versus the already-losing large-return reversal baseline, but did not create positive after-cost expectancy. The failure is broad across instruments, train/validation, validation halves, and predeclared sensitivities. Do **not** tune v1 using these outcomes.

Durable evidence: the original rejection record and rejected registry, plus the original sealed evidence/dataset in `orchestration/evidence/liquidity_meanrev_001_cache/`, descriptive audit `orchestration/evidence/disc_liquidity_meanrev_001_audit_20260919.json`, and `docs/research/liquidity_meanrev_001_audit_20260919.md`. Offline replay exactly matches the original complete selection object; it is not a new independent trial. All three cached series have zero hourly gaps. Validation also fails the base 20 bps cost proxy (-5.48 bps/trade). The frozen rule has no stop; additive label drawdown is not portfolio percentage or mark-to-market risk. No claim of validated profitability follows.

## DURABLE NEGATIVE MEMORY

Exact rejected fingerprints include at least:
- `DATA-BASIS-001`;
- `DATA-FUNDING-001`;
- `ACC-002`;
- `DISC-VOL-BREAKOUT-001-v1`;
- `DISC-LIQUIDITY-MEANREV-001-v1`.

Do not re-enter any exact rejected fingerprint into active selection/deep validation without materially new data or a genuinely different frozen scientific/economic hypothesis satisfying its recorded reconsideration conditions.

`DISC-RESIDUAL-MOMENTUM-001-v1` remains **deprioritized evidence-limited**, not terminally rejected, because its current-survivor universe prevents promotion-grade historical point-in-time interpretation. Its untouched OOS remains locked.

## CURRENT HIGHEST-VALUE CANDIDATE

The ranked queue has pivoted to **`DISC-SQUEEZE-RETENTION-001-v1`**, family `forced_flow_retention_momentum`.

Hypothesis-generation basis: Money Intelligence Sep. 19 observed BTC retaining the Sep. 18 upside move after the main short-liquidation impulse had normalized and explicitly queued a timestamp-safe matched squeeze sample. This is **generator evidence only**, not alpha evidence.

Economic hypothesis: after a large upside move initially amplified by short-covering, if forced-flow activity/leverage normalize while price retains the move, independent spot/capital demand may be carrying the move and continuation may have positive after-cost expectancy versus equally large price shocks without retention/deleveraging confirmation.

Target scope currently queued: liquid crypto; 1H / 4H / 24H research horizons. Before outcomes are inspected, the exact squeeze, forced-flow normalization, retention, entry, exit, hold, fixed instruments, chronology, matched baseline, costs, sample floors, search breadth, and multiple-testing treatment must be frozen. If timestamp-safe historical forced-flow/open-interest data are not genuinely available, block scientifically rather than fabricating or proxying them post hoc.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective capture verified, 79 members, no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — await sufficient matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate in the legacy data lane while its prospective maturation gate remains unmet. This does not block the separately authorized strategy-discovery lane. Load coordination through its canonical override loader; do **not** read only the base JSON.

The pivot has continued through a local data-capability preflight: `docs/research/squeeze_retention_data_preflight_20260919.md`. Existing derivatives history explicitly cannot provide defensible historical liquidation notional. DATA-003 must establish a bounded timestamp-defensible source before the next full contract is frozen and before any squeeze outcomes are examined. This is a local data deficiency, not proof that all free external sources are exhausted. No paid data was requested or acquired.

## CURRENT SPECIALIST EXECUTION QUEUE

The old liquidity tasks are closed DONE with their negative evidence. Active discovery assignments are now:

- `COORD-DISC-QUANT-003` — READY: freeze the exact squeeze-retention cheap-screen contract before outcome inspection.
- `COORD-DISC-VAL-003` — READY: independently falsify chronology, matched baseline, sample floors, multiple-testing and acceptance gates.
- `COORD-DISC-DATA-003` — READY: prove timestamp-safe historical price/open-interest/forced-flow data feasibility using free/approved sources; persist a precise blocker if unavailable.
- `COORD-DISC-TEST-003` — READY: adversarially test leakage, threshold/search expansion, OOS lock, rejected-memory and no-trade invariants.

Do not allow stale signal-era work or rejected fingerprints to consume these roles while this candidate is active in selection.

## SAFETY INVARIANTS

- Broker disconnected; no real-order authority.
- Existing $100,000 paper ledger remains authentic/append-only; never reset, reseed, rewrite, or cosmetically improve it.
- Code changes on isolated branches only.
- Confirmed defects get regression coverage where practical.
- Require exact-head **Security and Reliability** green before merge; runtime-affecting changes also require exact deployed-SHA verification.
- Missing, stale, malformed, future, ambiguous, provenance-uncertain, or scientifically insufficient evidence fails closed to WAIT / RESEARCH_ONLY.
- Never weaken chronology, purging, non-overlap, untouched OOS/forward boundaries, multiple-testing controls, point-in-time universe safety, cost realism, abstention, or promotion gates to obtain a pass.
- One promising backtest/OOS result grants no production, broker, paper-authority, or promotion authority.
- If the predefined rigorous evidence/validation criteria are genuinely satisfied, report that successful result clearly with exact supporting evidence and limitations.

## API / INFRASTRUCTURE STATE

The API-backed autonomous cloud specialist most recently paused cleanly because the OpenAI organization spend limit was exhausted. Do **not** add or increase OpenAI/Anthropic API spend merely to coordinate sessions. Prefer this scheduled Lead, GitHub state, deterministic Python/GitHub Actions, and already-approved infrastructure.

The previous Supabase egress incident remains bounded by merged query/window/throttling fixes. Do not reintroduce unbounded resolved-ledger polling or broad repeated database reads. The Supabase organization remains on the Free plan; do not upgrade without explicit user approval.

## LEGACY SIGNAL RETIREMENT / DATA HYGIENE

Legacy signal/dashboard production is now **retired, deployed and compacted**.

- PR #422 retired the scheduled 15-minute scan, legacy signal/system/paper dashboard routes, paid continuous-AI web observer, and legacy paper-trading runtime.
- No new legacy opportunity/forecast generation has occurred since the final pre-retirement scan at 2026-09-19 04:51Z.
- `crypto_opportunities` and `trading_signals` are truncated to **0 rows** and remain retired.
- PR #424 added safe prediction-ledger compaction: point-in-time universe snapshots are archived separately, compact `research_context` is preserved, resolved-summary reads no longer request full calibration JSON, and unresolved immutable forecasts remain untouched.
- Production compaction preserved **628** point-in-time universe snapshots and retains full calibration JSON for only the newest **2,000 resolved** forecasts plus unresolved forecasts.
- PR #428 fixes the durable migration contract discovered during production application: `prediction_ledger.calibration` is NOT NULL, so older resolved payloads compact to `{}::jsonb` rather than NULL; `research_context` is backfilled only when NULL to avoid repeat work.
- After `VACUUM FULL ANALYZE`, `prediction_ledger` is about **195 MB** and the total public Supabase relation footprint is about **204 MB**, down from roughly **488 MB** before cleanup.
- Current legacy ledger count is **112,462** forecasts, of which **27,052** remain unresolved; the temporary research-only resolver may let them mature but cannot generate new forecasts.
- Do not delete historical 2x+ event/control data, immutable experiment/rejection evidence, protected OOS/forward proof, or point-in-time provenance.
- Bulk historical research belongs in compressed Parquet/object storage + DuckDB/Polars rather than repeated large Supabase JSON reads.
- When the unresolved legacy ledger reaches zero, remove the temporary drain workflow and perform one final bounded compaction/space-reclaim pass if justified.

See `docs/LEGACY_SIGNAL_RETIREMENT.md`.


## 24/7 BACKGROUND MODEL ORCHESTRATION

The project now uses a machine-readable routing policy at `orchestration/model_routing_policy.json`.

- Deterministic Python/GitHub Actions handle repeatable screening, backtests, data transforms and state validation.
- OpenAI API `gpt-5.6-luna` handles routine bounded tasks.
- OpenAI API `gpt-5.6-terra` handles the autonomous quant-research lane for medium-complexity strategy research/implementation under the existing API budget.
- OpenAI API `gpt-5.6-sol` is reserved for deep scientific/Lead review where the expected information value justifies the higher cost; the autonomous Lead workflow already uses Sol for candidate review.
- **GPT-6 Astra is not an OpenAI API model.** It is routed only through ChatGPT Work/Codex. The canonical scheduled Work instructions live in `docs/ASTRA_BACKGROUND_WORKER.md`.
- The hourly **Trading Research Implementation Worker** and GitHub-event **Trading PR Follow-up Worker** are now created and enabled. Requested recurring execution preference is **Work → GPT-6 Astra → Medium**. The scheduler currently does not expose a verifiable model pin, so never claim the actual scheduled execution model is guaranteed.
- Background workers never use browser-tab scraping. GitHub remains the mailbox and source of truth.
- If Astra capacity is unavailable, the project must checkpoint the exact handoff and continue independent deterministic/API/Claude work rather than stall.

The OpenAI cloud specialist may own both `data-market` and `quant-research` READY tasks but remains strictly **one model run at a time**, one task per invocation, branch-isolated, budget-gated, unable to merge its own PR, and unable to trade. It selects the highest-priority READY ChatGPT-eligible task; after the current data task is complete, the squeeze-retention quant task becomes eligible automatically.

## FRIZZ / PLAYBIT EMA LANE

`DISC-FRIZZ-PLAYBIT-EMA-001-v1` remains `BLOCKED_SOURCE_FINGERPRINT`. The exact published indicator/source/rules must be pinned and fingerprinted before any screen. Never approximate it or silently substitute existing FFRIZZ logic.

## INDEPENDENT GENERATORS

Big-Move Intelligence and Money Intelligence may continue when they cannot contaminate protected evidence. Convert useful recurring findings into measurable, timestamp-defensible, predeclared hypotheses rather than narratives. Current generator evidence for squeeze-retention came from `money_intelligence/research_cycles/2026-09-19T0357Z-cycle.json`.

## CURRENT INTEGRATION / CI STATE

PR #416 is the single integration vehicle for this milestone; no competing
liquidity screen was opened. Its original frozen contract and first negative
artifact are preserved. Current-main background routing from PR #417
(`0b0e715`) was integrated without changing its models, budgets or authority.

The audit repairs stale `*-002` routing assertions after the `*-003` pivot,
restores historical rejection/provenance fields and machine-readable AI_STATE
headings, validates supplied contracts against the pinned original hash, rejects
hourly gaps and replaces repeated live-history selection runs with offline
exact replay. It adds return distribution/frequency diagnostics without new gates.

Original screen Security & Reliability run `35420353639` and selection run
`35420353644` passed on `e652d458401d40d45e098c85680ef96ddbd8ce51`.
Those runs do not authorize merging later changes. GitHub checks on the final
PR #416 head are authoritative for final full-suite, security, dependency,
secret, replay and supervisor validation; the PR body records their exact IDs
when complete. Require a fresh exact-head check before any merge.

## EXACT NEXT STEP

1. Continue `DISC-SQUEEZE-RETENTION-001-v1` without opening outcomes. PR #423 proved the sampled free archive is structurally real but still insufficient for a frozen screen because publication chronology, missing-hour semantics, full historical coverage and venue-unit semantics are not yet defensible.
2. Resolve `COORD-DISC-DATA-003` first: establish timestamp/publication-safe price + OI + forced-flow/liquidation history, or persist a precise scientific blocker. Do not proxy missing liquidation history with future/current data.
3. Only after the data contract is defensible may QUANT/VAL/TEST freeze the full squeeze-retention scientific contract and run train/validation. Untouched OOS remains locked and no central deep candidate exists.
4. Independent Big-Move Intelligence should continue studying **2x+ events within 90 days** with matched non-movers and point-in-time precursors. Money Intelligence may continue independent hypothesis generation without contaminating protected strategy evidence.
5. Keep legacy signal/dashboard production retired. Let the temporary pending-prediction drain finish existing immutable rows; no new legacy forecasts are permitted.


## STATUS VOCABULARY

Do not conflate:
- IMPLEMENTED;
- TESTED;
- MERGED;
- DEPLOYED;
- BACKTESTED;
- OOS TESTED;
- ROBUSTNESS TESTED;
- CROSS-ENGINE VERIFIED;
- FORWARD TESTED;
- LIVE TESTED;
- VALIDATED PROFITABLE.

The project currently has **no validated profitable strategy** and **no live-money authority**.

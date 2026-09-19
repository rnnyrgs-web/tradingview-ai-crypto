# AI_STATE.md

Last reconciled: 2026-09-19T04:12Z
Last updated: 2026-09-19T04:12Z

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

Durable evidence: `orchestration/evidence/disc_liquidity_meanrev_001_20260919.json` and `orchestration/rejected_fingerprints.json`.

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

## CURRENT SPECIALIST EXECUTION QUEUE

The old liquidity tasks are closed DONE with their negative evidence. Active discovery assignments are now:

- `COORD-DISC-QUANT-003` — READY: freeze the exact squeeze-retention cheap-screen contract before outcome inspection.
- `COORD-DISC-VAL-003` — READY: independently falsify chronology, matched baseline, sample floors, multiple-testing and acceptance gates.
- `COORD-DISC-DATA-003` — READY: prove timestamp-safe historical price/open-interest/forced-flow data feasibility using free/approved sources; persist a precise blocker if unavailable.
- `COORD-DISC-TEST-003` — READY: adversarially test leakage, threshold/search expansion, OOS lock, rejected-memory and no-trade invariants.

Do not allow stale signal-era work or rejected fingerprints to consume these roles while this candidate is active in selection.

## API / INFRASTRUCTURE STATE

The API-backed autonomous cloud specialist most recently paused cleanly because the OpenAI organization spend limit was exhausted. Do **not** add or increase OpenAI/Anthropic API spend merely to coordinate sessions. Prefer this scheduled Lead, GitHub state, deterministic Python/GitHub Actions, and already-approved infrastructure.

The previous Supabase egress incident remains bounded by merged query/window/throttling fixes. Do not reintroduce unbounded resolved-ledger polling or broad repeated database reads. The Supabase organization remains on the Free plan; do not upgrade without explicit user approval.

## FRIZZ / PLAYBIT EMA LANE

`DISC-FRIZZ-PLAYBIT-EMA-001-v1` remains `BLOCKED_SOURCE_FINGERPRINT`. The exact published indicator/source/rules must be pinned and fingerprinted before any screen. Never approximate it or silently substitute existing FFRIZZ logic.

## INDEPENDENT GENERATORS

Big-Move Intelligence and Money Intelligence may continue when they cannot contaminate protected evidence. Convert useful recurring findings into measurable, timestamp-defensible, predeclared hypotheses rather than narratives. Current generator evidence for squeeze-retention came from `money_intelligence/research_cycles/2026-09-19T0357Z-cycle.json`.

## CURRENT INTEGRATION / CI STATE

PR #416 owns the liquidity-screen implementation, evidence preservation, durable rejection, queue pivot, and specialist reconciliation.

Important chronology during this Lead cycle:
- branch was created from `037706ece4cd0c20e0e161ebaf0014caf8b52c46`;
- `main` independently advanced to unsigned Money Intelligence commit `e55f42cba404d7d795c0ee9820ffa2fd08e65313`; that change is independent hypothesis-generation research and did not alter trading authority;
- exact PR head `e652d458401d40d45e098c85680ef96ddbd8ce51` passed Security & Reliability run `35420353639` and Liquidity Mean Reversion Selection run `35420353644`;
- subsequent evidence/queue/rejected-memory/coordination/AI_STATE commits changed the PR head, so **the final head must pass exact-head Security & Reliability again before merge**;
- because the strategy queue and rejected registry changed, Strategy Discovery Supervisor validation must also pass before treating the pivot as canonical.

Do not merge on an earlier green SHA.

## EXACT NEXT ACTION

1. Verify PR #416 final head and current `main` have no conflicting ownership change.
2. Require exact-head Security & Reliability success on the final PR head.
3. Require Strategy Discovery Supervisor validation to accept the rejected-memory removal plus new `DISC-SQUEEZE-RETENTION-001-v1` ranked screen.
4. If those gates pass, merge PR #416 with an exact-head guard and verify the resulting canonical `main` SHA.
5. On the next discovery cycle, start with `COORD-DISC-DATA-003` data-feasibility proof plus `COORD-DISC-QUANT-003` frozen pre-outcome contract. Do not inspect squeeze outcomes until the contract/data semantics are fixed.

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

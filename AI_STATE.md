# AI_STATE.md

Last reconciled: 2026-09-19T05:29Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. On every run, verify actual `main` first, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, the ranked strategy-discovery queue, rejected-fingerprint registry, specialist coordination plus all override layers, `orchestration/model_routing_policy.json`, current Big-Move/Money Intelligence evidence, open PRs, and exact-head CI. GitHub/persistent machine-readable state outranks chat memory.

## PRIMARY OBJECTIVE

Find and rigorously validate one algorithmic strategy with sustainable positive after-cost expectancy and useful frequency, while independently improving scientifically defensible 90-day large-upside / 2x-candidate intelligence. Do not call backtests real profit and do not manufacture a 2x forecast.

Exactly one candidate may consume expensive deep-validation capacity at a time. Cheap predeclared screening may reject many candidates. Failure means: explain -> preserve evidence -> learn -> pivot -> continue. A waiting lane must not block independent useful work that cannot contaminate protected evidence.

## CURRENT CANONICAL STRATEGY STATE

- No validated profitable strategy exists.
- Discovery lifecycle: **SELECTION**.
- `active_deep_candidate`: **null**.
- Current ranked candidate: **`DISC-SQUEEZE-RETENTION-001-v1`** (`forced_flow_retention_momentum`).
- Untouched OOS: **LOCKED / unopened**.
- Genuine forward evidence for this candidate: **not opened**.
- Broker/live authority: **OFF**; research/paper/shadow only.
- Combined variable paid-project ceiling: approximately **$30/month total** unless the user explicitly changes it.

Economic hypothesis: after an upside move initially amplified by short covering, continuation may have positive after-cost expectancy when forced-flow/leverage normalize while price retains the move, consistent with independent spot/capital demand. This remains a hypothesis, not alpha evidence.

Before any strategy outcomes are inspected, freeze exact squeeze/forced-flow normalization, retention, entry, exit, hold, instruments, chronology, matched baseline, realistic costs/stress, sample floors, search breadth, and multiple-testing treatment. Never replace missing historical forced-flow data with future/current snapshots or post-hoc proxies.

## DATA-003 RESULT AND CURRENT DATA TASK

`COORD-DISC-DATA-003` is **DONE** via PR #423. Its decision is **`INSUFFICIENT_FOR_FROZEN_SCREEN`**, not a strategy rejection and not a data-contract pass.

Verified bounded sample:
- venue: Binance USDⓈ-M;
- instruments: BTCUSDT / ETHUSDT / SOLUSDT;
- receipt hour: `2026-09-02T12:00Z`;
- object families: liquidations / open_interest / mark_price;
- objects verified: **9/9**;
- bytes verified: **336,805**;
- strategy outcomes inspected: **false**;
- untouched OOS opened: **false**.

Still unproved for promotion-grade research:
- exact historical coverage and cross-file gap/duplicate behavior;
- independently defensible archive/publication chronology for historical objects;
- exact Binance contract/base/quote and liquidation-notional unit semantics;
- completeness of public liquidation broadcasts, which may only be usable as a declared lower-bound proxy.

`COORD-DISC-DATA-004` is now **READY** and is the highest-value data-market action. Its job is to resolve or terminally falsify timestamp-safe historical data availability without inspecting strategy returns.

DATA-004 rules:
- predeclare the exact historical interval before outcomes;
- first use bounded zero-new-cost exact file/prefix enumeration or an equivalent complete manifest/gap audit;
- if CryptoHFTData cannot establish the contract, investigate only timestamp-defensible alternatives preserving the same frozen Binance USDⓈ-M BTC/ETH/SOL semantics;
- never silently substitute another venue/instrument;
- distinguish source absence, collection outage, and zero published liquidation events;
- never fabricate missing liquidation flow as zero;
- freeze decision-time chronology using receipt/public-availability semantics;
- keep strategy returns and untouched OOS unopened;
- if no defensible zero-new-cost path exists, persist a precise terminal data blocker and pivot rather than rescuing the fingerprint with a post-hoc proxy;
- no new paid service without explicit approval.

## CURRENT SPECIALIST EXECUTION QUEUE

Canonical coordination must be loaded through `orchestration/coordination_overrides.py`, which applies the historical override ledger and the Lead reconciliation layer.

Current active discovery assignments for `DISC-SQUEEZE-RETENTION-001-v1`:
- `COORD-DISC-DATA-004` — **READY**: resolve or terminally falsify timestamp-safe data availability.
- `COORD-DISC-QUANT-003` — **READY**: independent pre-outcome scientific contract work; if timestamp-safe forced-flow data remain unavailable, block scientifically rather than proxying.
- `COORD-DISC-VAL-003` — **READY**: independently falsify chronology, matched baseline, sample floors, multiple-testing and acceptance gates.
- `COORD-DISC-TEST-003` — **READY**: adversarially test leakage, search expansion, OOS lock, rejected-memory and no-trade invariants.

Independent pre-outcome quant/validation/audit work may continue while DATA-004 is unresolved. It may not open outcomes or weaken the data firewall.

## RECENT CANONICAL COORDINATION CHANGE

PR #426 merged safely after exact-head validation.
- exact PR head: `28626e74a7db98ffe694ed316d9b08f6a73bb43e`;
- Security & Reliability run `35423941357`: **SUCCESS**;
- Liquidity Mean Reversion Selection run `35423941355`: **SUCCESS**;
- verified merge commit: `deb71c7e6db9a0d59f6513060acc1f69472c5abb`.

PR #426 does not add profitability evidence. It reconciles the durable mailbox so stale DATA-003 execution stops and DATA-004 becomes the actionable data-market task while the scientific firewall remains intact.

## DURABLE NEGATIVE MEMORY

Do not rescue rejected exact fingerprints without materially new data or a genuinely different frozen scientific/economic hypothesis. Rejected exact fingerprints include at least:
- `ACC-002`;
- `DATA-BASIS-001`;
- `DATA-FUNDING-001`;
- `DISC-VOL-BREAKOUT-001-v1`;
- `DISC-LIQUIDITY-MEANREV-001-v1`.

`DISC-RESIDUAL-MOMENTUM-001-v1` remains evidence-limited/deprioritized rather than terminally rejected because the current-survivor universe prevents promotion-grade point-in-time interpretation. Its untouched OOS remains locked.

The liquidity-shock mean-reversion rejection remains durable: 0/3 passing fixed instruments; pooled train and validation expectancy were materially negative at 3x costs; untouched OOS stayed locked. Do not tune that v1 using its rejected outcomes.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective point-in-time capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for enough genuinely matured independent prospective cohorts.

This legacy breadth maturation wait does not block strategy discovery.

## 90-DAY BIG-MOVE / MONEY INTELLIGENCE LANE

Big-Move Intelligence and Money Intelligence remain independent hypothesis/evidence generators when they cannot contaminate protected strategy evidence.

Rules:
- study historical large-upside / roughly-2x-within-90-days events against matched pre-event controls;
- use point-in-time-safe universes where possible;
- optimize for precision/lift, PR-AUC/calibration, forward returns, tradability and regime stability rather than raw accuracy;
- label OBSERVED FACT / INFERENCE / HYPOTHESIS / FORECAST / UNKNOWN;
- preserve failed precursors and never rewrite them after outcomes;
- never retroactively call an already-moved asset an early prediction;
- only produce a ranked Big-Move Evidence Profile when current evidence is strong enough to support it.

There is currently **no promotion-grade 90-day 2x candidate** in canonical state. Recent Money Intelligence observations remain generator evidence unless converted into predeclared matched-control tests.

## FRIZZ / PLAYBIT EMA LANE

`DISC-FRIZZ-PLAYBIT-EMA-001-v1` remains **BLOCKED_SOURCE_FINGERPRINT**. Pin/fingerprint the exact published indicator/source/rules before any screen. Never approximate it or silently substitute existing FFRIZZ logic.

## COST / INFRASTRUCTURE / MODEL ROUTING

- Obey `orchestration/model_routing_policy.json`.
- Deterministic Python/GitHub Actions first when possible.
- API routing uses GPT-5.6 Luna/Terra/Sol only within approved budgets.
- GPT-6 Astra belongs to ChatGPT Work/Codex, not the OpenAI API; never claim an API Astra run.
- One autonomous cloud specialist run at a time; branch-isolated; cannot merge itself or trade.
- Do not add OpenAI/Anthropic spend merely to relay work between sessions.
- Supabase Pro is approved, but the egress/query/window/throttling safeguards from PRs #413/#414 remain mandatory; do not reintroduce unbounded resolved-ledger polling or broad repeated reads.

## SAFETY / SCIENTIFIC INVARIANTS

- Broker disconnected; no real-order authority or fund transfer.
- Do not rewrite historical predictions, frozen OOS, genuine-forward evidence, or rejected fingerprints.
- Isolated branches only for code/state changes.
- Exact-head **Security & Reliability** must pass before merge.
- Runtime-affecting changes also require actual deployed-SHA verification.
- Missing/stale/malformed/future/ambiguous/provenance-uncertain evidence fails closed to WAIT / RESEARCH_ONLY.
- Never weaken chronology, purging, non-overlap, point-in-time universe safety, realistic costs, robustness, multiple-testing controls, or promotion gates to obtain a pass.
- One attractive backtest/OOS result grants no production or live authority.
- If frozen rigorous criteria genuinely pass, report the success clearly with exact evidence and limitations.

## EXACT NEXT ACTION

Execute **`COORD-DISC-DATA-004`** as the primary data-market task: establish one bounded, timestamp-defensible historical data contract for the frozen Binance BTCUSDT/ETHUSDT/SOLUSDT squeeze-retention inputs, or persist a precise terminal blocker and pivot to the next materially distinct available-data hypothesis. Do not inspect strategy outcomes or untouched OOS during source resolution.

In parallel, independent QUANT-003 / VAL-003 / TEST-003 pre-outcome work may continue only within their existing evidence firewalls. If DATA-004 succeeds, freeze the full scientific contract before any cheap screen. If it fails, preserve why and pivot without post-hoc source substitution.

## STATUS VOCABULARY

Do not conflate IMPLEMENTED / TESTED / MERGED / DEPLOYED / BACKTESTED / OOS TESTED / ROBUSTNESS TESTED / CROSS-ENGINE VERIFIED / FORWARD TESTED / LIVE TESTED / VALIDATED PROFITABLE.

Current truth: **no validated profitable strategy, no promotion-grade 90-day 2x candidate, untouched OOS locked for the active squeeze-retention candidate, broker/live authority off.**
